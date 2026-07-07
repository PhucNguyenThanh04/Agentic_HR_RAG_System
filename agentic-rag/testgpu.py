import torch

print("PyTorch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("CUDA device name:", torch.cuda.get_device_name(0))
print("PyTorch can use CUDA:", torch.cuda.is_available())
print("PyTorch can use MPS (Apple Silicon):", torch.backends.mps.is_available())
