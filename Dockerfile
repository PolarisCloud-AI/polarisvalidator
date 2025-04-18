 # Use an official Python runtime as a base image
 FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . /app

# Install the project in editable mode
RUN pip install -e .

# Expose any necessary ports (optional, if the validator needs to communicate externally)
EXPOSE 8080
# Define the default command to run the validator script
CMD ["sh", "-c", "python neurons/validator.py --netuid 49 --wallet.name $WALLET_NAME --wallet.hotkey $WALLET_HOTKEY"]