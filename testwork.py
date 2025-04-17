import paramiko
import os

def connect_to_remote_machine(host, port=22, username="user"):
    # Initialize SSH client
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Path to your private key
    key_path = os.path.join(os.path.dirname(_file_), "ssh_host_key")
    
    try:
        # Connect using the private key
        client.connect(
            hostname=host,
            port=port,
            username=username,
            key_filename=key_path,
            timeout=5
        )
        
        print(f"Successfully connected to {username}@{host}:{port}")
        
        # Execute a command
        stdin, stdout, stderr = client.exec_command("hostname")
        print(f"Remote hostname: {stdout.read().decode().strip()}")
        
        # Close the connection
        client.close()
        return True
        
    except Exception as e:
        print(f"Failed to connect: {str(e)}")
        return False

# Example usage
connect_to_remote_machine("192.168.1.100", username="admin")