import pprint
import re
import sys
import os
import yaml
from typing import List, Dict, Tuple, Any

def parse_jcl_output(filename: str) -> List[Dict[str, str]]:
    devices: List[Dict[str, str]] = []
    current_device: str | None = None

    device_pattern = re.compile(r'^Port forwarding for (\S+)$')
    ssh_forward_pattern = re.compile(
        r'^ +Forwarding traffic ([\d\.]+):(\d+) --> [\d\.]+:22$'
    )

    with open(filename, 'r') as f:
        second:bool = False 
        for line in f:
            line = line.rstrip()
            device_match = device_pattern.match(line)
            if device_match:
                current_device = device_match.group(1)
                continue

            ssh_match = ssh_forward_pattern.match(line)
            if ssh_match and current_device: 
                if second: # second occurence of the same device
                    ssh_host = ssh_match.group(1)
                    ssh_port = ssh_match.group(2)
                    devices.append({
                        'device_name': current_device,
                        'ssh_host': ssh_host,
                        'ssh_port': ssh_port
                    })
                    current_device = None  # Reset current device after processing
                    second = False
                else:    
                    second = True
                    
    return devices

def parse_output2host_ini(filename: str) -> List[Tuple[str, int, str]]:
    """
    Returns a list of mapping rules:
    Each rule is a tuple: (regex, order, hostname)
    """
    rules: List[Tuple[str, int, str]] = []
    rule_pattern = re.compile(r'^(\S+)\s+(\d+)\s+(\S+)$')
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith(';'):
                continue
            m = rule_pattern.match(line)
            if m:
                regex, order, hostname = m.groups()
                rules.append((regex, int(order), hostname))
    return rules

def map_devices_to_hostnames(
    devices: List[Dict[str, str]],
    rules: List[Tuple[str, int, str]]
) -> Dict[str, Dict[str, str]]:
    """
    devices: list of dicts with 'device_name', 'ssh_host', 'ssh_port'
    rules: list of (regex, order, hostname)
    Returns: dict of hostname -> info
    """
    mapped: Dict[str, Dict[str, str]] = {}
    for regex, order, hostname in rules:
        count = 0
        for device in devices:
            if re.match(regex, device['device_name']):
                count += 1
                if count == order:
                    mapped[hostname] = {
                        'ssh_host': device['ssh_host'],
                        'ssh_port': device['ssh_port'],
                        'device_name': device['device_name']
                    }
     #               break  
    return mapped

def write_host_vars_yaml(hostname: str, info: Dict[str, str], out_dir: str = "host_vars") -> None:
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, f"{hostname}.yml")
    # Load existing YAML if it exists
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            try:
                data = yaml.safe_load(f) or {}
            except Exception:
                data = {}
    else:
        data = {}
    # Update only the relevant variables
    data["ansible_ssh_host"] = info["ssh_host"]
    data["ansible_ssh_port"] = info["ssh_port"]
    with open(filepath, "w") as f:
        yaml.dump(data, f, default_flow_style=False)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <jcl_output2.txt> <output_dir> [output2host.ini]")
        sys.exit(1)
    jcl_file: str = sys.argv[1]
    output_dir: str = sys.argv[2]
    ini_file: str = sys.argv[3] if len(sys.argv) > 3 else "output2host.ini"
    devices = parse_jcl_output(jcl_file)
    rules = parse_output2host_ini(ini_file)
    pprint.pprint(devices)
    mapped = map_devices_to_hostnames(devices, rules)
    for hostname, info in mapped.items():
        fname = os.path.join(output_dir,"host_vars",f"{hostname}.yml")
        print(f"Writing {fname}: ssh_host={info['ssh_host']} ssh_port={info['ssh_port']}")
        write_host_vars_yaml(hostname, info, os.path.join(output_dir, "host_vars"))