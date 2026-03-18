# ford-qemu-toolkit
Boot Ford's new ECG2 (Enhanced Central Gateway) in QEMU.
<img width="516" height="392" alt="Screenshot_2026-03-17_at_11 53 12_PM" src="https://github.com/user-attachments/assets/531460c0-1f50-499f-b790-b3dc5576b6da" />

```sh
git clone https://github.com/BlueOvalLabs/ford-qemu-toolkit
cd ford-qemu-toolkit
git submodule update --init --recursive
python3 -m venv .venv 
source ./.venv/bin/activate
pip install -r ./requirements.txt
make
```
