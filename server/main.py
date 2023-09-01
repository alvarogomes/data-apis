from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from minio import Minio
import subprocess
import socket
import json
import httpx
import os
import uvicorn

app = FastAPI()

minioClient = Minio("minio:9000", access_key="minio",
                    secret_key="minio123", secure=False)

SERVICES_JSON_PATH = "services.json"
services = {}  # service_name: subprocess
service_ports = {}  # service_name: Port


def find_available_port(start=18001, end=18999):
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            socket_available = s.connect_ex(('localhost', port))
            if socket_available:
                return port
    return None


def update_services_json():
    with open(SERVICES_JSON_PATH, "w") as f:
        json.dump(list(service_ports.items()), f)


def load_services():
    global services, service_ports
    if os.path.exists(SERVICES_JSON_PATH):
        with open(SERVICES_JSON_PATH, "r") as f:
            service_list = json.load(f)
            service_ports = {k: v for k, v in service_list}


def create_folder_if_not_exists(folder_name: str):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)


def execute_command(command: str):
    try:
        process = subprocess.Popen(command, shell=True)
        print("Comando executado com sucesso.")
        return process
    except Exception as e:  # Popen pode lançar um Exception genérico se falhar
        print(f"Erro ao executar o comando: {e}")
        return None


@app.on_event("startup")
async def startup_event():
    found = minioClient.bucket_exists("mybucket")
    if not found:
        minioClient.make_bucket("mybucket")
    else:
        print("Bucket 'mybucket' already exists")

    load_services()
    for service_name in service_ports:
        await start_service(service_name)


@app.on_event("shutdown")
async def shutdown_event():
    for service_name in service_ports:
        await stop_service(service_name)


@app.post("/v1/api/create")
async def create_service(service_name: str, file_py: UploadFile = File(...), file_req: UploadFile = File(...)):
    if service_name in services:
        return {"message": "Service name already exists"}

    port = find_available_port()
    if not port:
        return {"message": "No available port"}

    py_file_path = f"./services/{service_name}/{service_name}.py"
    req_file_path = f"./services/{service_name}/requirements.txt"

    create_folder_if_not_exists(f"./services/{service_name}")

    # Adding OpenTelemetry Configuration
    original_code = file_py.file.read().decode()
    
    modified_code = original_code

    with open(py_file_path, "w") as buffer:
        buffer.write(modified_code)
    with open(req_file_path, "wb") as buffer:
        buffer.write(file_req.file.read())

    minioClient.fput_object(
        "mybucket", f"services/{service_name}/{service_name}.py", py_file_path)
    minioClient.fput_object(
        "mybucket", f"services/{service_name}/requirements.txt", req_file_path)

    subprocess.run(["pip", "install", "-r", req_file_path])
    
    process = execute_command(
        "cd ./services/{} && opentelemetry-instrument --id_generator random --traces_exporter console,otlp --metrics_exporter console  --service_name {} uvicorn {}:app --port {}".format(service_name, service_name, service_name, str(port)))
    
    services[service_name] = process
    service_ports[service_name] = port

    update_services_json()

    return {"message": f"Service started at http://localhost:{port}/", "service_name": service_name}


@app.post("/v1/api/stop/{service_name}")
async def stop_service(service_name: str):
    if service_name not in services:
        raise HTTPException(status_code=404, detail="Service not found")

    services[service_name].terminate()
    del services[service_name]
    update_services_json()
    return {"message": "Service stopped"}


@app.post("/v1/api/start/{service_name}")
async def start_service(service_name: str):
    if service_name in services:
        raise HTTPException(
            status_code=400, detail="Service is already running")

    port = service_ports.get(service_name)
    if not port:
        raise HTTPException(status_code=404, detail="Service not found")

    process = execute_command(
        "cd ./services/{} && opentelemetry-instrument --id_generator random --traces_exporter console,otlp --metrics_exporter console --service_name {} uvicorn {}:app --port {}".format(service_name, service_name, service_name, str(port)))
    services[service_name] = process

    update_services_json()

    return {"message": "Service started"}


@app.post("/v1/api/restart/{service_name}")
async def restart_service(service_name: str):
    await stop_service(service_name)
    await start_service(service_name)
    return {"message": "Service restarted"}


@app.delete("/v1/api/remove/{service_name}")
async def remove_service(service_name: str):
    await stop_service(service_name)

    minioClient.remove_object("mybucket", f"services/{service_name}/main.py")
    minioClient.remove_object(
        "mybucket", f"services/{service_name}/requirements.txt")
    os.remove(f"services/{service_name}/{service_name}.py")
    os.remove(f"services/{service_name}/requirements.txt")

    del service_ports[service_name]
    update_services_json()

    return {"message": "Service removed"}


@app.get("/v1/api/list_services")
async def list_services():
    return {"services": list(service_ports.items())}


@app.get("/service/{service_name}/{path:path}")
@app.post("/service/{service_name}/{path:path}")
@app.put("/service/{service_name}/{path:path}")
@app.patch("/service/{service_name}/{path:path}")
@app.delete("/service/{service_name}/{path:path}")
async def gateway(service_name: str, path: str, request: Request):
    port = service_ports.get(service_name)
    if not port:
        raise HTTPException(status_code=404, detail="Service not found")

    method = request.method
    headers = dict(request.headers)
    params = dict(request.query_params)
    body = await request.body()

    async with httpx.AsyncClient() as client:
        try:
            r = await client.request(
                method=method,
                url=f"http://localhost:{port}/{path}",
                headers=headers,
                params=params,
                content=body,
            )
            r.raise_for_status()

            content_type = r.headers.get("Content-Type")

            if "application/json" in content_type:
                return JSONResponse(content=r.json(), status_code=r.status_code)
            elif "text/html" in content_type:
                return HTMLResponse(content=r.text, status_code=r.status_code)
            else:
                return JSONResponse(content={"message": "Unknown Content-Type"}, status_code=415)
        except httpx.RequestError as e:
            return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=18000)
