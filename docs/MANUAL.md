# slurmtop user manual

[繁體中文](MANUAL.zh-TW.md) · [Back to the README](../README.md)

slurmtop shows CPU, memory, disk, network and GPU usage for one machine or a
whole cluster, who holds each GPU, and the Slurm queue. You can read it in a
terminal, in a browser, in Grafana, as JSON, or as a recorded report.

## Contents

1. [Install](#1-install)
2. [First run](#2-first-run)
3. [Reading the terminal view](#3-reading-the-terminal-view)
4. [Jobs, owners and idle GPUs](#4-jobs-owners-and-idle-gpus)
5. [The browser dashboard](#5-the-browser-dashboard)
6. [Prometheus and Grafana](#6-prometheus-and-grafana)
7. [JSON output](#7-json-output)
8. [Performance reports](#8-performance-reports)
9. [All options](#9-all-options)
10. [Platform notes](#10-platform-notes)
11. [Troubleshooting](#11-troubleshooting)
12. [Security](#12-security)
13. [FAQ](#13-faq)

---

## 1. Install

slurmtop is one file. It needs **Python 3.8 or newer** on the machine where you
run it, and nothing else — no pip packages.

### Linux and macOS

```bash
curl -fsSL https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.sh | bash
```

The installer puts `slurmtop` in `/usr/local/bin` if it can write there (or has
passwordless `sudo`), otherwise in `~/.local/bin`, and tells you how to add
that to your `PATH` if needed. To choose the directory yourself:

```bash
curl -fsSL https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.sh | bash -s -- ~/bin
```

Or copy the file by hand — that is all the installer does:

```bash
curl -fsSLo ~/bin/slurmtop https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/slurmtop
chmod +x ~/bin/slurmtop
```

### Windows

Install Python 3.8+ from python.org or the Microsoft Store, then in PowerShell:

```powershell
irm https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.ps1 | iex
```

This puts `slurmtop.py` and a `slurmtop.cmd` launcher into
`%LOCALAPPDATA%\slurmtop` and prints the command to add that folder to your
`PATH` (it does not change any settings itself). You can also skip the
installer and run `py slurmtop.py` from wherever you saved the file.

### Clusters without internet access

Download the file on your laptop and copy it over:

```bash
scp slurmtop login-node:~/bin/
```

Only the machine you run slurmtop on needs it. The other nodes are read over
SSH and nothing is installed on them.

### Uninstall

Delete the file (`rm "$(command -v slurmtop)"`, or the `%LOCALAPPDATA%\slurmtop`
folder on Windows). slurmtop does not create any other files unless you ask
for them with `--log` or `--html`.

---

## 2. First run

### Just this machine

```bash
slurmtop --nodes localhost
```

No SSH and no Slurm needed. This works on a laptop or workstation running
Linux, macOS, FreeBSD or Windows.

### A Slurm cluster

```bash
slurmtop
```

The nodes come from `sinfo`. The node you are on is read directly, and the
others are read over SSH. The queue is read from `squeue`.

### A list of machines

```bash
slurmtop --nodes gpu01,gpu02,gpu03
slurmtop --ssh-config                 # every Host in ~/.ssh/config
slurmtop --ssh-config ~/.ssh/lab.conf --nodes extra-box
```

`--ssh-config` uses every `Host` name in the file. It skips patterns containing
`*`, `?` or `!` and `Match` blocks, and does not follow `Include`. Host
aliases work because slurmtop simply runs `ssh <name>`.

### SSH requirements

For every remote node, `ssh <node> true` must work **without a password
prompt** (a key in `ssh-agent`, or a key without a passphrase). slurmtop uses
`BatchMode=yes`, so it never waits for a prompt. It also reuses one
connection per node through ControlMaster (not on Windows, whose OpenSSH does
not support it), so a refresh costs one round trip per node.

The remote side needs a POSIX `sh`. bash is used when it is there but is not
required. It does not matter whether the login shell is bash, zsh, fish or
csh.

### Stopping

Press Ctrl-C. The terminal view runs in the alternate screen, so your previous
terminal content comes back.

---

## 3. Reading the terminal view

```
◤ SLURMTOP // lab-h200 ──────────────────────────────────────────── 12:42:45 ◥   ← title (Slurm ClusterName or host name) and clock
  ▁▂▄▅▆▇█▁▁▁▁▁▁▁▁    CORE  20/32 online                                          ← busy GPUs / all GPUs
  46.2% UTIL         PWR 11.57 kW   MEM 1908/4493 GiB   THRM 80°C  ▲ THERMAL      ← power, GPU memory, hottest GPU
  · ▄▄▄▄▄▄▄▄▄▄▄▄     GRID  ▉▉▉▉▉▉▉▉  │  ▉▉▉▉▉▉▉▉  │  ▉▉▉▉▁▁▁▁                   ← one cell per GPU, grouped by node
  ⚠ gpu02 G5 hot 80°C · gpu04 G0,G1 held but idle (4103 chen)                     ← alert line (only when something is wrong)
╭┤ LOAD // last 30 samples ├───────────────────────────────────────────────╮     ← cluster GPU utilisation over time
╭┤ NODE gpu01 ◉ LOCAL ├──────── 8/8 busy · 853G · 4.7 kW · 71°C ╮                  ← one panel per node
│ CPU ▕██░░░░░░░░░░░░▏  14.8% ▲ ▁▂▃▂▁▂▃▄ load 20 30 28           │
│ MEM ▕█████░░░░░░░░░▏  33.9%   684/2015 GiB                      │
│ DSK ▕██████░░░░░░░░▏  42.9%   738G/1.7T   NET ↓ 582M/s ↑ 56.4M/s│
│ G0 ▕████████░░░░▏  67% ▁▂▄▆█▆▄▂  85.6G 59°  488W 4101 hawks     │  ← GPU: bar, %, history, memory, temp, power, job, user
╰──────────────────────────────────────────────────────────────────╯
╭┤ Slurm queue ├────────────────────────────────────────────────────╮
│      JOB  NAME        USER     STATE   ELAPSED   PROG     LEFT   N  CPU  GPU  WHERE
│     4101  llama-ft    hawks    ● run   5h12m     ██░░░░░░ 18h48m 2  256    8  gpu[01-02]
```

### Colours and symbols

| You see | It means |
|---|---|
| `▕███░░░▏` | a bar, green → yellow → red as the value rises |
| `▁▂▃▅▇` after a value | its history over the last samples |
| `▲` / `▼` | rising or falling compared with the last few samples |
| arc gauge at top left | cluster GPU utilisation (CPU on a cluster without GPUs) |
| `◉` next to a node | node status light, coloured by its load |
| tinted node background | the node is busy: amber from 45 %, orange from 75 %, red from 90 % |
| `-` in a field | the value could not be read (e.g. `[N/A]` from nvidia-smi under MIG) |
| `stale 12s` in a node title | that node missed the refresh deadline; its last reading is shown (see below) |
| `IDLE` in a GPU row | a job holds this GPU but has not used it (see [section 4](#4-jobs-owners-and-idle-gpus)) |
| `4101 hawks` at the end of a GPU row | the job holding the GPU and who submitted it; `4101+1` means two jobs |
| `(root)` at the end of a GPU row | a process outside Slurm, and its owner |
| `Apple M3 10-core` at the end of a GPU row | an unowned GPU's model name |
| `◆ FULL LOAD` | the cluster average is at 90 % or more |
| `▲ THERMAL` | the hottest GPU is at 78 °C or more |

![node panels tinted by load](../zone.png)

### The alert line

It lists, worst first: unreachable nodes, GPUs at 78 °C or more, root disks at
90 % or more, nodes showing stale data, and GPUs held but idle. Whatever does
not fit becomes `+N more`. When everything is fine, the line is not shown at
all.

### Slow or hung nodes

Each refresh waits at most `--node-timeout` seconds per node (6 by default, 20
with `--once`). A node that misses the deadline keeps showing its last reading,
marked `stale Ns`, and every other node keeps updating. After 60 seconds
without fresh data the node is shown as unreachable. A stuck fetch is not
restarted while it is still running, so a hung node cannot pile up SSH
sessions.

### The queue

| Column | Meaning |
|---|---|
| JOB / NAME / USER | Slurm job id (`1006_3` for array tasks), name, user |
| STATE | `● run`, `◌ pend`, or Slurm's state code |
| ELAPSED / LEFT | run time so far and time left before the limit |
| PROG | share of the time limit already used; turns red near the end |
| N / CPU / GPU | nodes, CPUs, GPUs requested |
| WHERE | node list for running jobs, the reason for pending ones |

Below the jobs, one line per node shows Slurm's view: state, allocated CPUs,
idle CPUs and free memory. A long queue is split into two or three columns
when that saves height. On a machine without Slurm the queue section is left
out. If Slurm is installed but `squeue` does not answer, the queue says
*squeue is not responding*.

### Layout options

- By default nothing is hidden. The frame may be taller than the window, and
  spare height goes to the LOAD chart.
- `--fit` squeezes everything onto one screen. It gives things up in this
  order: sparklines, per-GPU rows (one summary line per node), queue columns,
  and finally trailing jobs.
- `--dense` shows one line per node. This happens on its own when the node
  panels would need more than the screen height minus 12 lines.
- `--stack` puts the node panels under each other.
- `--proc` lists up to 8 GPU processes per node (pid, memory, name).
- `--me` keeps only your own jobs and GPUs; the header still covers the whole
  cluster.

### Animations, fonts and colours

- By default the screen only changes when the data changes. `--flair` turns on
  the effects: border traces, a scan sweep in bars, breathing and blinking
  alerts, heat plumes (`≋ ≈ ~`) next to hot GPUs, spinning job markers and a
  boot splash. `--no-splash` skips just the splash.
- `--no-color` prints plain text; `--ascii` uses ASCII bars and sparklines for
  fonts without block characters.
- If the output encoding cannot show box characters at all (a Windows console
  redirected to a file, `LANG=C`), the whole screen switches to ASCII
  automatically.
- `--lang zh` switches to Traditional Chinese; this is the default when `LANG`
  is `zh_TW`, `zh_HK` or `zh_CN`.
- `--qr` prints a QR code for the project page, and `--qr-panel` shows it
  beside the queue.

---

## 4. Jobs, owners and idle GPUs

slurmtop combines two sources so a GPU is attributed even when nothing runs
on it:

1. On each node, for every process nvidia-smi reports, it reads
   `/proc/<pid>/cgroup` and takes `job_<id>` from it. This works with cgroup
   v1 and v2. Processes outside Slurm are shown with their owner.
2. On the machine running slurmtop, `scontrol -d -o show job` says which GPU
   indices each running job was given on each node, e.g.
   `GRES=gpu:h200:4(IDX:0-3)`.

**Held but idle**: a GPU is flagged when a job owns it and its utilisation has
stayed below 5 % for `--idle-samples` fresh samples in a row (default 30,
which is one minute at the default 2-second interval). The count restarts
when the GPU gets used, changes hands, becomes unreadable, or when the node's
data is stale. Lower the number to catch idle GPUs sooner:

```bash
slurmtop --idle-samples 10
```

AMD and Jetson GPUs get owners through the Slurm allocation only (source 2).

---

## 5. The browser dashboard

```bash
slurmtop --web                 # listens on 127.0.0.1:8765
slurmtop --web 9000            # another port
slurmtop --web 0.0.0.0:8765    # every interface — read "Exposing it" first
```

The page shows cluster totals, the alert list, a cluster utilisation chart and
one card per node. Each card has CPU, memory, disk and network, and for every
GPU a bar with history, memory, temperature, power, owner and the `IDLE`
badge. The queue is at the bottom. The page refreshes itself at the `-n`
interval, follows your browser's light or dark setting, and works on a phone.
It loads nothing from the internet.

### Viewing it from your laptop

Run slurmtop on the login node and open an SSH tunnel from your laptop:

```bash
ssh -N -L 8765:localhost:8765 login-node
# then open http://localhost:8765 in your browser
```

slurmtop prints this command when it starts.

### Keeping it running

A systemd user unit is enough:

```ini
# ~/.config/systemd/user/slurmtop.service
[Unit]
Description=slurmtop web dashboard
[Service]
ExecStart=%h/.local/bin/slurmtop --web 127.0.0.1:8765 -n 5
Restart=on-failure
[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload && systemctl --user enable --now slurmtop
loginctl enable-linger "$USER"     # keep it running after you log out (if allowed)
```

### Exposing it

The dashboard has **no login**. Anyone who can reach the port sees node
names, job names and user names. When it listens on anything other than
localhost, slurmtop prints a warning. To share it, put it behind a web server
that authenticates, for example nginx with basic auth:

```nginx
location /slurmtop/ {
    auth_basic "slurmtop";
    auth_basic_user_file /etc/nginx/slurmtop.htpasswd;
    proxy_pass http://127.0.0.1:8765/;
    proxy_set_header Host localhost;
}
```

The page uses relative URLs, so it works under a sub-path. The
`Host localhost` line is needed because a localhost-only slurmtop refuses
requests with a foreign `Host` header (this blocks DNS-rebinding attacks).

### Endpoints

| Path | Content |
|---|---|
| `/` | the dashboard |
| `/api/state` | the latest sample as JSON (same as `--json`, plus UI strings) |
| `/metrics` | Prometheus text format |
| `/healthz` | `ok` |

Until the first sample is ready, `/api/state` and `/metrics` answer 503.

---

## 6. Prometheus and Grafana

```yaml
# prometheus.yml
scrape_configs:
  - job_name: slurmtop
    scrape_interval: 15s
    static_configs:
      - targets: ["login-node:8765"]
```

(Run slurmtop with `--web 0.0.0.0:8765` for this, or scrape through a
tunnel or proxy.)

| Metric | Labels | Meaning |
|---|---|---|
| `slurmtop_node_up` | node | 1 if the node answered (possibly stale), 0 if unreachable |
| `slurmtop_node_stale_seconds` | node | age of the reading shown for a stale node |
| `slurmtop_cpu_utilization_percent` | node | CPU utilisation |
| `slurmtop_memory_used_bytes`, `_memory_total_bytes` | node | RAM |
| `slurmtop_load1` | node | 1-minute load average |
| `slurmtop_disk_used_bytes`, `_disk_total_bytes` | node | root filesystem |
| `slurmtop_network_receive_bytes_per_second`, `_transmit_…` | node | physical interfaces |
| `slurmtop_gpu_utilization_percent` | node, gpu, vendor | GPU utilisation |
| `slurmtop_gpu_memory_used_bytes`, `_memory_total_bytes` | node, gpu, vendor | GPU memory |
| `slurmtop_gpu_temperature_celsius`, `slurmtop_gpu_power_watts` | node, gpu, vendor | |
| `slurmtop_gpu_idle_held` | node, gpu, vendor | 1 if held but idle |
| `slurmtop_gpu_owner_info` | node, gpu, vendor, job, user | always 1; join on it to label GPUs with jobs |
| `slurmtop_jobs` | state | jobs in the queue per state |

Useful queries:

```promql
avg(slurmtop_gpu_utilization_percent)                                    # cluster average
sum by (user) (slurmtop_gpu_owner_info)                                   # GPUs per user
sum(slurmtop_gpu_idle_held)                                               # GPUs held but idle
slurmtop_gpu_utilization_percent * on(node, gpu) group_left(job, user) slurmtop_gpu_owner_info
```

---

## 7. JSON output

```bash
slurmtop --json > sample.json
slurmtop --json | jq '.nodes[] | .name as $n | .gpus[]? | select(.idle_held) | {node: $n, gpu: .index, job, user}'
```

Top level: `version`, `time` (Unix seconds), `cluster`, `summary`, `nodes`,
`slurm` (is Slurm installed), `slurm_down`, `queue`, `queue_stale_s`, `alerts`,
`history`.

- `summary`: `nodes`, `nodes_up`, `gpus`, `gpus_busy`, `gpu_util`, `power_w`,
  `gpu_temp_max`, `vram_used_mib`, `vram_total_mib`, `cpu_pct`, `mem_used_mib`,
  `mem_total_mib`.
- each node: `name`, `up`, `stale_s`, `local`, `cpu_pct`, `load`, `cpus`,
  `mem_used_mib`, `mem_total_mib`, `disk {pct, used, total}`,
  `net {rx, tx}` (bytes/s, `null` on the first sample), `gpus`, `history`.
- each GPU: `index`, `uuid`, `vendor` (`nvidia`, `amd`, `apple`, `jetson`),
  `model`, `util`, `mem_used_mib`, `mem_total_mib`, `temp_c`, `power_w`, `job`,
  `user`, `idle_held`, `history`.
- each queued job: `id`, `job_id` (the real id, which differs for array tasks),
  `name`, `state`, `user`, `elapsed`, `left`, `limit` (as Slurm prints them),
  `elapsed_s`, `left_s`, `limit_s` (seconds), `nodes`, `cpus`, `gpus`, `gres`,
  `where`.

Units are raw, and anything that could not be read is `null`. `--me` applies
here too.

---

## 8. Performance reports

`--report` records samples and then summarises them.

```bash
slurmtop --report 600                             # ten minutes, then a summary
slurmtop --report -- python train.py --epochs 3   # exactly as long as the command runs
slurmtop --report 600 --html run.html             # also a single-file HTML report with charts
slurmtop --report 600 --json > run.json           # the summary as JSON
slurmtop --report 600 --log run.csv               # also every raw sample as CSV
```

When you wrap a command, slurmtop starts it, samples until it exits, and then
exits with **the command's exit code** (128+N if the command was killed by
signal N). This makes it safe to use in scripts. Ctrl-C stops the recording
and still prints the report; the wrapped command is stopped as well. Bad
`--log` or `--html` paths are reported before anything starts.

### Inside a Slurm job

```bash
#!/bin/bash
#SBATCH --gres=gpu:4
slurmtop --nodes "$(hostname -s)" --report --html "report-$SLURM_JOB_ID.html" -- srun python train.py
```

### What the numbers mean

| Column | Meaning |
|---|---|
| avg / p95 / max | GPU utilisation: mean, 95th percentile, peak |
| busy | share of samples in which the GPU was above 5 % |
| mem max | peak GPU memory used |
| temp max | peak temperature |
| avg power | mean power draw |
| energy | power integrated over time (trapezoid rule; gaps longer than 2.5 sample intervals are not bridged) |
| held idle | how long the GPU was flagged as held but idle |
| JOB | jobs seen on the GPU during the recording |

Per node the report gives average and peak CPU and peak memory. At the bottom
it gives the cluster GPU average and the total GPU energy. Stale readings are
left out of every figure.

### The HTML report

`--html FILE` writes one self-contained page: summary tiles, the cluster
utilisation chart, one chart per node with a line per GPU, and the tables. The
charts are drawn as SVG when the report is written, so the file needs no
JavaScript or internet access. You can mail it, attach it to a ticket or keep
it in a repository.

### The CSV log

`--log FILE` appends one row per node and one per GPU for every sample. It
works in the live view, with `--web` and with `--report`. The header is
written only when the file is new.

`time, node, kind (node|gpu), gpu, vendor, util_pct, mem_used_mib,
mem_total_mib, temp_c, power_w, job, user, idle_held, disk_pct, net_rx_bps,
net_tx_bps`

For `kind=node` rows, `util_pct` is CPU utilisation. For example, average GPU
utilisation per user with nothing but Python:

```python
import csv, collections
use = collections.defaultdict(list)
for r in csv.DictReader(open("run.csv")):
    if r["kind"] == "gpu" and r["user"] and r["util_pct"]:
        use[r["user"]].append(float(r["util_pct"]))
for user, v in sorted(use.items()):
    print(f"{user:10} {sum(v) / len(v):5.1f}%  over {len(v)} GPU-samples")
```

---

## 9. All options

| Option | Default | What it does |
|---|---|---|
| `-n SEC`, `--interval SEC` | 2 | refresh interval |
| `--once` | | print one frame and exit |
| `--web [ADDR:]PORT` | 127.0.0.1:8765 | browser dashboard, `/api/state`, `/metrics` |
| `--json` | | print one sample as JSON and exit |
| `--report [SEC]` | | record SEC seconds, or the command after `--`, then summarise |
| `--html FILE` | | with `--report`: also write an HTML report |
| `--log FILE` | | append every sample to a CSV file |
| `--nodes A,B,C` | from Slurm | which machines to show (`localhost` = this one, no SSH) |
| `--ssh-config [PATH]` | ~/.ssh/config | add every Host in an ssh config |
| `--title TEXT` | ClusterName / host name | header title |
| `--me` | | only your jobs and the GPUs they hold |
| `--idle-samples N` | 30 | samples below 5 % before a held GPU is flagged idle |
| `--node-timeout SEC` | 6 (20 with `--once`) | per-node deadline per refresh |
| `--proc` | | list GPU processes |
| `--stack` | | node panels vertically |
| `--dense` | automatic | one line per node |
| `--fit` | | squeeze into one screen |
| `--no-color` | | plain text |
| `--ascii` | automatic if needed | ASCII bars |
| `--flair` | | animations and boot splash |
| `--no-splash` | | with `--flair`, skip the splash |
| `--lang en\|zh` | from `LANG` | interface language |
| `--qr`, `--qr-wide`, `--qr-panel` | | QR code for the project page |
| `-V`, `--version` | | print the version |

---

## 10. Platform notes

**Linux.** CPU from `/proc/stat`, memory from `free`, disk from `df /`,
network from `/proc/net/dev`. Network counts only physical interfaces: it
leaves out `lo`, container and bridge interfaces, VPN tunnels, bond members
and VLAN / IPoIB child interfaces, so traffic is not counted twice.

- **NVIDIA:** `nvidia-smi`.
- **AMD:** read straight from the amdgpu driver in sysfs (utilisation, VRAM,
  temperature, power); no ROCm tools needed.
- **NVIDIA Jetson:** GPU load and temperature from sysfs; memory is shared
  with the CPU.
- **Intel GPUs:** not read yet.

**macOS.** CPU from `top`, memory from `vm_stat`, network from `netstat -ib`.
Disk is the data volume (`/System/Volumes/Data`), since `/` is the read-only
system volume. GPUs come from `ioreg` without sudo: on Apple Silicon,
utilisation and unified-memory use; on Intel Macs, the integrated GPU and AMD
discrete GPUs, including temperature and power. On Apple Silicon, temperature
and power need `sudo powermetrics`, so they show `-`.

**FreeBSD.** CPU from `kern.cp_time`, memory from `vm.stats`, network from
`netstat -ibn` (columns are located from the header line).

**Windows.** The local machine is read through the Win32 API (CPU, memory),
`shutil.disk_usage` (system drive), `netstat -e` (network) and
`nvidia-smi.exe` (NVIDIA GPUs). Remote Linux nodes are read with the built-in
OpenSSH client. Windows Terminal and the classic console both work; colours
are switched on automatically.

---

## 11. Troubleshooting

**A node shows "unreachable".** Try `ssh -o BatchMode=yes <node> true` from the
same machine. If it asks for a password or fails, fix SSH first (keys,
`known_hosts`). Then check that the node has `sh` and `nvidia-smi` in the
non-interactive `PATH`: `ssh <node> 'command -v nvidia-smi'`.

**A node keeps showing "stale".** It answers, but slower than `--node-timeout`.
nvidia-smi can be slow when persistence mode is off
(`sudo nvidia-smi -pm 1`). You can also raise the deadline:
`--node-timeout 15`.

**GPU values show "-".** nvidia-smi reported `[N/A]`. This is normal for
utilisation under MIG and for power on some boards.

**No GPUs are shown.** Run `nvidia-smi` on that node. For AMD, check that
`/sys/class/drm/card*/device/gpu_busy_percent` exists. Without any GPU the
node is shown as CPU-only, and the header gauge switches to CPU.

**The GPU owner is empty but the GPU is busy.** The process may be outside
Slurm (it shows as `(user)`), or `/proc` may be mounted with `hidepid`, which
hides other users' processes. The Slurm allocation still attributes allocated
GPUs.

**Boxes or question marks instead of bars.** Your font lacks block characters.
Use `--ascii`.

**Garbage like `←[H` on Windows.** You are on a very old console without VT
support. Use Windows Terminal, or run with `--once --no-color`.

**The browser says "forbidden host".** A localhost-only slurmtop refuses a
foreign `Host` header. If you are behind a proxy, add
`proxy_set_header Host localhost;`.

**"cannot serve on …: Address already in use".** Another program has the
port. Choose another one: `--web 8799`.

**The queue says "squeue is not responding".** The Slurm controller is slow or
down. slurmtop keeps the last queue for up to a minute, marked stale.

---

## 12. Security

- slurmtop only reads. On the nodes it runs a short read-only shell script:
  `nvidia-smi`, `/proc`, `/sys`, `df`, `netstat`. It writes files only when you
  ask for them with `--log` or `--html`.
- Job names, user names and process names are chosen by other users. Control
  characters are stripped from them before anything is drawn, so a job name
  cannot move your cursor, change your window title or write your clipboard.
- The browser page inserts all of that data as text only. It sends a strict
  Content-Security-Policy, uses no inline script, and on localhost refuses
  requests whose `Host` header is not localhost.
- `--web` has no authentication. Keep it on localhost and use an SSH tunnel,
  or put an authenticating proxy in front of it.

---

## 13. FAQ

**Does it need root?** No. Everything it reads is readable by normal users.

**Does it put load on the nodes?** Each refresh runs one short shell script per
node over an existing SSH connection. Use `-n 5` or more on very large fleets.

**Can it keep history across restarts?** The live history is kept in memory.
Use `--log` for a permanent record, or Prometheus.

**Can several people use the web dashboard?** Yes. Any number of browsers can
open it, and they all share the one sampler.

**Is there keyboard control?** Not yet. Use options, and Ctrl-C to quit.

**How do I contribute?** The tests use only the standard library:
`python3 -m unittest discover -s tests -t .`. Recorded tool output lives in
`tests/fixtures/`, so GPUs and Slurm are not needed. See `NIGHT_LOG.md` for
the development notes.
