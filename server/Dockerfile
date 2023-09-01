# Use the official image as a parent image
FROM python:3.8-slim-buster

# Set the working directory
WORKDIR /usr/src/app

# Install any needed packages specified in requirements.txt
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container
COPY . .

# Make port available to the world outside this container
EXPOSE 18000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "18000"]
