# gpu_specs.py
GPU_WEIGHTS = {
    # NVIDIA Datacenter GPUs
    "H200 SXM": 1.10,            
    "B100 SXM": 1.20,            
    "B200 SXM": 1.25,             
    "Blackwell Ultra": 1.30,      
    "Grace Blackwell GB200": 1.35,
    "H100 SXM": 1.00, 
    "H100 PCIe": 0.94,  
    "A100 SXM": 0.56,  
    "A100 PCIe": 0.50,  
    "L40": 0.31,       
    "A40": 0.16,       
    "A30": 0.06,      
    "Tesla T4": 0.06,  
    "V100 SXM": 0.25,  
    "V100 PCIe": 0.22, 
    "A800 SXM": 0.50,  
    "L4": 0.10,       
    "H200 SXM": 1.10,  
    "A800 PCIe": 0.45, 
    "Tesla P100": 0.15, 
    "RTX Pro 6000 Blackwell": 0.48,
    "RTX Pro 5000 Blackwell": 0.38,
    "RTX Pro 4000 Blackwell": 0.18,
    "RTX 5090": 0.30,
    "RTX 5080": 0.20,
    "RTX 5070 Ti": 0.14,
    "RTX 5070": 0.12,
    "RTX 5060 Ti": 0.10,
    "RTX 5060": 0.08,
    "RTX 5050": 0.05,
    "Radeon RX 9070 XT": 0.07,
    "Radeon RX 9070": 0.06,
    "Arc Pro B60": 0.06,
    "Arc Pro B50": 0.05,
    "Arc B580": 0.04,
    "Arc B570": 0.03,

    # NVIDIA Consumer/Professional GPUs
    "RTX 6000 Ada": 0.28,  # $0.90/hr
    "RTX A6000": 0.23,     # $0.75/hr
    "RTX 4090": 0.16,      # $0.50/hr
    "RTX 4080": 0.08,      # $0.25/hr (Vast.ai)
    "RTX 4070": 0.04,      # $0.12/hr (Vast.ai)
    "RTX 4060 Ti": 0.16,   # $0.12/hr (Vast.ai)
    "RTX 4060": 0.02,      # $0.07/hr (Vast.ai)
    "RTX 3080": 0.06,      # $0.20/hr
    "RTX 3070": 0.05,      # Estimated, $0.16/hr
    "RTX 3060": 0.04,      # Estimated, $0.12/hr
    "RTX 2080 Ti": 0.05,   # Estimated, $0.16/hr
    "RTX 2070": 0.03,      # Estimated, $0.10/hr
    "GTX 1080 Ti": 0.04,   # Estimated, $0.12/hr
    "GTX 1660 Super": 0.03, # Estimated, $0.10/hr
    "Titan RTX": 0.10,     # Estimated, $0.32/hr
    "Quadro RTX 8000": 0.20, # Estimated, $0.64/hr
    "RTX 4070 Ti": 0.04,   # $0.12/hr (Salad)
    "RTX 3090": 0.09,      # $0.28/hr (Vast.ai)
    "RTX 2060": 0.03,      # Estimated, $0.10/hr
    "GTX 1070": 0.03,      # Estimated, $0.09/hr
    "RTX 3050": 0.02,      # Estimated, $0.06/hr
    "Quadro P5000": 0.08,  # Estimated, $0.25/hr
    "Titan V": 0.09,       # Estimated, $0.28/hr

    # AMD GPUs
    "Radeon RX 7900 XTX": 0.08,  # Estimated, $0.25/hr
    "Radeon RX 7900 XT": 0.07,   # Estimated, $0.22/hr
    "Radeon RX 6900 XT": 0.06,   # Estimated, $0.20/hr
    "Radeon RX 6800": 0.05,      # Estimated, $0.16/hr
    "Radeon Pro W6800": 0.07,    # Estimated, $0.22/hr
    "Instinct MI250": 0.50,      # Estimated, competes with A100
    "Instinct MI210": 0.40,      # Estimated, slightly below MI250
    "Radeon RX 6700 XT": 0.04,   # Estimated, $0.12/hr
    "Radeon RX 5700 XT": 0.03,   # Estimated, $0.10/hr
    "Radeon RX 6600 XT": 0.03,   # Estimated, $0.09/hr
    "Radeon Pro W5700": 0.05,    # Estimated, $0.16/hr
    "Radeon VII": 0.06,          # Estimated, $0.20/hr

    # Intel GPUs
    "Arc A770": 0.02,       # Estimated, $0.06/hr
    "Arc A750": 0.02,       # Estimated, $0.06/hr
    "Data Center GPU Max 1550": 0.30,  # Estimated, competes with L40
    "Data Center GPU Flex 170": 0.15,  # Estimated, lower-end datacenter
    "Arc A580": 0.02,       # Estimated, $0.05/hr
}



def get_gpu_weight(gpu_name: str) -> float:
    """
    Retrieve the weight of a specified GPU by matching the input name or its substring.
    Matches inputs like 'NVIDIA GeForce RTX 4060 Ti' to 'RTX 4060 Ti' in the dictionary.
    
    Args:
        gpu_name (str): Name of the GPU (e.g., 'NVIDIA GeForce RTX 4060 Ti' or 'RTX 4060 Ti').
        
    Returns:
        float: Weight of the GPU (0-1), or 0.0 if not found.
    """
    # Normalize input by removing common prefixes and converting to lowercase
    normalized_name = gpu_name.lower().replace("nvidia geforce", "").replace("nvidia", "").strip()
    
    # Try exact match first
    if gpu_name in GPU_WEIGHTS:
        return GPU_WEIGHTS[gpu_name]
    
    # Try substring match
    for key in GPU_WEIGHTS:
        # Check if the key (e.g., 'RTX 4060 Ti') is a substring of the normalized input
        if key.lower() in normalized_name:
            return GPU_WEIGHTS[key]
    
    return 0.0
