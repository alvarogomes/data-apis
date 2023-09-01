import click
import httpx
import os

@click.group()
@click.option('--server', default='http://localhost:18000', help='Endereço do servidor.')
@click.pass_context
def cli(ctx, server):
    """CLI para gerenciar serviços FastAPI."""
    ctx.ensure_object(dict)
    ctx.obj['SERVER'] = server

@click.command()
@click.argument('service_name')
@click.option('--file-py', default='main.py', help='Caminho para o arquivo Python. Padrão é main.py.')
@click.option('--file-req', default='requirements.txt', help='Caminho para o arquivo requirements.txt. Padrão é requirements.txt.')
@click.pass_context
def create(ctx, service_name, file_py, file_req):
    """Cria um novo serviço FastAPI."""
    server = ctx.obj['SERVER']
    url = f"{server}/v1/api/create"
    with open(file_py, 'rb') as pyf, open(file_req, 'rb') as reqf:
        response = httpx.post(url, files={'file_py': pyf, 'file_req': reqf}, params={'service_name': service_name})
    print(response.json())

@click.command()
@click.pass_context
def list(ctx):
    """Lista todos os serviços FastAPI ativos."""
    server = ctx.obj['SERVER']
    url = f"{server}/v1/api/list_services"
    response = httpx.get(url)
    print(response.json())

@click.command()
@click.argument('service_name')
@click.pass_context
def stop(ctx, service_name):
    """Para um serviço FastAPI existente."""
    server = ctx.obj['SERVER']
    url = f"{server}/v1/api/stop/{service_name}"
    response = httpx.post(url)
    print(response.json())

@click.command()
@click.argument('service_name')
@click.pass_context
def restart(ctx, service_name):
    """Reinicia um serviço FastAPI existente."""
    server = ctx.obj['SERVER']
    url = f"{server}/v1/api/restart/{service_name}"
    response = httpx.post(url)
    print(response.json())

@click.command()
@click.argument('service_name')
@click.pass_context
def remove(ctx, service_name):
    """Remove um serviço FastAPI existente."""
    server = ctx.obj['SERVER']
    url = f"{server}/v1/api/remove/{service_name}"
    response = httpx.delete(url)
    print(response.json())

cli.add_command(create)
cli.add_command(list)
cli.add_command(stop)
cli.add_command(restart)
cli.add_command(remove)

if __name__ == '__main__':
    cli(obj={})
