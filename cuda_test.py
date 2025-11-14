import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
print("END LATEST/n/n/n/n")


# import torch

# print("torch version:", torch.__version__)
# print("cuda available:", torch.cuda.is_available())
# print("compiled with cuda:", torch.version.cuda)
# # print("cuda runtime version:", torch._C._cuda_getCompiledVersion())
# # print("cuda driver version:", torch._C._cuda_getDriverVersion())
# print("device count:", torch.cuda.device_count())
# if torch.cuda.is_available():
#     print("device name:", torch.cuda.get_device_name(0))


# import torch, sys

# print(torch.__file__)
# print(sys.executable)

# import torch

# try:
#     x = torch.randn(1000, 1000).cuda()
#     print("Tensor moved to CUDA successfully:", x.device)
# except Exception as e:
#     print("FAILED:", e)
