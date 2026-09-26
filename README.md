# slurmtop

**See every GPU in your lab — in the terminal, in the browser, or in a report —
with one file and nothing to install on the nodes.**

[繁體中文說明](README.zh-TW.md) · [User manual](docs/MANUAL.md) · [使用手冊](docs/MANUAL.zh-TW.md)

`slurmtop` is a single Python script (standard library only, Python 3.8+) that
shows CPU, memory, disk, network and per-GPU utilisation for every node, who
holds each GPU, and the Slurm queue. It reads other machines over plain SSH, so
there is no agent, no database and no daemon to set up.

![slurmtop in the terminal](demo.gif)

![slurmtop --web in the browser](docs/web-dashboard.png)

*Top: the terminal view (recorded with `--flair`). Bottom: `slurmtop --web` in
a browser. Both show simulated load on H200 nodes — same code path, synthetic
telemetry — so the pictures are reproducible.*

## Why people use it

- **One glance answers "who is using the GPUs, and are they actually busy?"**
  Every GPU row ends with the job and user holding it, and GPUs that a job
  holds but leaves idle are flagged — even when nothing is running on them.
- **Works where you are.** A terminal over SSH, a browser tab, Grafana, a JSON
  pipe or a report you can mail: one refresh feeds all of them.
- **Nothing to deploy.** Copy one file to the machine you sit at. Nodes need
  only SSH and a POSIX `sh`; nothing is installed or left running on them.
- **Honest about problems.** A node that hangs is shown as `stale 12s` while
  the others keep updating; unreachable nodes, hot GPUs and full disks go into
  one alert line at the top.
- **Measures performance, not just watches it.** `--report` records a run and
  gives average / p95 / peak utilisation, memory, temperature, power and
  energy per GPU — wrap any command and get an HTML report with charts.

## Quick start

```bash
curl -fsSL https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.sh | bash

slurmtop                     # a Slurm cluster: nodes are found automatically
slurmtop --nodes localhost   # just this machine (laptop, workstation)
slurmtop --ssh-config        # every host in ~/.ssh/config
slurmtop --web               # the same in your browser at http://127.0.0.1:8765
```

Windows (PowerShell): `irm https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.ps1 | iex`,
then `slurmtop --nodes localhost` or `slurmtop --web`.

## Four ways to look at the same data

| You want… | Run | You get |
|---|---|---|
| a live view in the terminal | `slurmtop` | node panels, per-GPU bars and history, owners, alerts, the queue |
| a live view in a browser, on a phone, on a wall screen | `slurmtop --web` | a self-contained dashboard (no CDN, works offline) |
| graphs in Grafana, alerts in Prometheus | `slurmtop --web`, scrape `/metrics` | node and per-GPU metrics, owner info, jobs by state |
| to evaluate a training run or a benchmark | `slurmtop --report -- python train.py` | a summary table, plus `--html` charts and `--log` CSV |
| data for your own scripts | `slurmtop --json` | one sample as JSON, raw units |

![a --report HTML page](docs/report.png)

## Runs on

| Machine | CPU · memory · disk · network | GPUs | Tested on |
|---|---|---|---|
| Linux | ✓ | NVIDIA (`nvidia-smi`), AMD (amdgpu sysfs, no ROCm tools needed), NVIDIA Jetson | NVIDIA: the H200 Slurm cluster it was first built for (earlier version); AMD, Jetson and the newest features: recorded output |
| macOS | ✓ | Apple Silicon and Intel-Mac GPUs via `ioreg` (no sudo) | a real M3 MacBook |
| Windows 10/11 | ✓ | NVIDIA (`nvidia-smi.exe`) | a real Windows 11 PC with an RTX 4070 Ti SUPER |
| FreeBSD | ✓ | NVIDIA if `nvidia-smi` is installed | recorded output |
| any node with SSH | read over SSH with a POSIX `sh` script | as above | bash, dash, ksh, sh; zsh, csh, tcsh logins |

The machine you run it from needs Python 3.8+. With Slurm, jobs and the queue
are shown; without it, everything else still works. Terminals without Unicode
get a plain ASCII screen automatically.

## Everyday recipes

```bash
slurmtop --me                          # only my jobs and the GPUs they hold
slurmtop --dense                       # one line per node for big fleets (automatic when needed)
slurmtop --once                        # print one frame, e.g. to paste into chat
slurmtop --report 600 --html run.html  # record ten minutes, keep an HTML report
slurmtop --log usage.csv               # keep every sample as CSV while watching
slurmtop --lang zh                     # 繁體中文介面
```

In a batch script, wrap the step you want to evaluate:

```bash
slurmtop --nodes "$(hostname -s)" --report --html "report-$SLURM_JOB_ID.html" -- srun python train.py
```

Everything is explained in the [user manual](docs/MANUAL.md): every option,
how to read each part of the screen, the browser dashboard behind an SSH
tunnel or a reverse proxy, Prometheus and Grafana, reports, troubleshooting.

<details>
<summary>What the terminal view looks like, as text</summary>

```
◤ SLURMTOP // lab-h200 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────── 12:43:04 ◥
  ▁▂▄▅▆▇█▁▁▁▁▁▁▁▁    CORE  20/32 online
  46.2% UTIL         PWR    11.57 kW   MEM   1908/4493 GiB   THRM  80°C  ▲ THERMAL
  · ▄▄▄▄▄▄▄▄▄▄▄▄     GRID  ▉▉▉▉▉▉▉▉  │  ▉▉▉▉▉▉▉▉  │  ▉▉▉▉▁▁▁▁  │  ▁▁▁▁▁▁▁▁
  ⚠ gpu02 G5 hot 80°C · gpu04 G0,G1 held but idle (4103 chen)
╭┤ LOAD // last 30 samples ├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ ·····························│················································································································· │
│ ·····························│················································································································· │
│ ▂▂▂▁▁▁  ·····················│················································································································· │
│ ████████▇▇▇▆▆▅▅▅▅▅▄▄▄▄▅▅▅▅▅▅▆▆················································································································· │
│ ██████████████████████████████················································································································· │
│ ██████████████████████████████················································································································· │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭┤ NODE gpu01 ◉ LOCAL ├ 8/8 busy · 853G · 4.7 kW╮╭┤ NODE gpu02 ◉ SSH ├ 8/8 busy · 932G · 5.1 kW ·╮╭┤ NODE gpu03 ◉ SSH ├ 4/8 busy · 115G · 1.1 kW ·╮
│ CPU ▕██░░░░░░░░░░░░▏  14.8% ▲ load 20 30 28   ││ CPU ▕█████░░░░░░░░░▏  37.3% ▲ load 30 30 28   ││ CPU ▕██░░░░░░░░░░░░▏  14.8% ▲ load 40 30 28   │
│ MEM ▕█████░░░░░░░░░▏  33.9%   684/2015 GiB    ││ MEM ▕██████░░░░░░░░▏  41.2%   830/2015 GiB    ││ MEM ▕███████░░░░░░░▏  48.5%   977/2015 GiB    │
│ DSK  42.9%   NET ↓  582M/s ↑ 56.4M/s          ││ DSK  46.3%   NET ↓  547M/s ↑ 56.5M/s          ││ DSK  49.4%   NET ↓  323M/s ↑ 56.6M/s          │
│ G0 ▕████████░░░░▏  67%   85.6G 59°  488W 4101 ││ G0 ▕█████████░░░▏  78%   99.4G 63°  556W 4101 ││ G0 ▕████░░░░░░░░▏  31%   40.3G 46°  267W 4102 │
│ G1 ▕████████░░░░▏  70%   89.4G 60°  507W 4101 ││ G1 ▕██████████░░▏  84%  107.4G 66°  595W 4101 ││ G1 ▕███░░░░░░░░░▏  24%   31.2G 43°  223W 4102 │
│ G2 ▕█████████░░░▏  75%   95.6G 62°  537W 4101 ││ G2 ▕███████████░▏  90%  115.1G 68°  632W 4101 ││ G2 ▕██░░░░░░░░░░▏  17%   23.2G 41°  183W 4102 │
│ G3 ▕██████████░░▏  81%  103.4G 65°  575W 4101 ││ G3 ▕███████████░▏  95%  121.2G 70°  662W 4101 ││ G3 ▕█░░░░░░░░░░░▏  12%   16.6G 39°  151W 4102 │
│ G4 ▕██████████░░▏  87%  111.4G 67°  614W 4101 ││ G4 ▕████████████▏  97%  124.7G 71°  679W 4101 ││ G4 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
│ G5 ▕███████████░▏  93%  118.4G 69°  649W 4101 ││ G5 ▕████████████▏  98%  125.2G 80°  682W 4101 ││ G5 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
│ G6 ▕████████████▏  96%  123.3G 71°  673W 4101 ││ G6 ▕████████████▏  96%  122.4G 70°  668W 4101 ││ G6 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
│ G7 ▕████████████▏  98%  125.4G 71°  682W 4101 ││ G7 ▕███████████░▏  91%  117.0G 69°  641W 4101 ││ G7 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
╰───────────────────────────────────────────────╯╰───────────────────────────────────────────────╯╰───────────────────────────────────────────────╯
╭┤ NODE gpu04 ◉ SSH ├ 0/8 busy · 8G · 0.6 kW · 3╮
│ CPU ▕█████░░░░░░░░░▏  37.3% ▲ load 50 30 28   │
│ MEM ▕████████░░░░░░▏  55.7%   1123/2015 GiB   │
│ DSK  52.1%   NET ↓  116M/s ↑ 56.6M/s          │
│ G0 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W IDLE │
│ G1 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W IDLE │
│ G2 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
│ G3 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
│ G4 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
│ G5 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
│ G6 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
│ G7 ▕░░░░░░░░░░░░▏   0%    1.0G 34°   75W      │
╰───────────────────────────────────────────────╯
╭┤ Slurm queue ├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│     JOB NAME      USER   STATE  ELAPSED PROG  LEFT   GPU WHERE              JOB NAME      USER   STATE  ELAPSED PROG  LEFT   GPU WHERE          │
│    4101 llama-ft  hawks  ● run  5h12m   █░░░░ 18h48m  8 gpu[01-02]         4102 diffusion lin    ● run  1h40m   ██░░░ 2h20m   4 gpu03           │
│    4103 notebook  chen   ● run  3h05m   ██░░░ 4h55m   2 gpu04              4104 eval-swee wu     ◌ pend 0s      ░░░░░ 6h00m   4 (Resources)     │
│    4105 cfd-mesh  chen   ◌ pend 0s      ░░░░░ 12h00m  - (Priority)                                                                              │
│ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ │
│  gpu01      mixed    CPU ▕███████░░░▏ 160/224 idle 64   RAM free 725 GiB                                                                        │
│  gpu02      mixed    CPU ▕███████░░░▏ 160/224 idle 64   RAM free 725 GiB                                                                        │
│  gpu03      mixed    CPU ▕███████░░░▏ 160/224 idle 64   RAM free 725 GiB                                                                        │
│  gpu04      mixed    CPU ▕███████░░░▏ 160/224 idle 64   RAM free 725 GiB                                                                        │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
  Ctrl-C quit  ·  --proc processes  ·  --stack vertical  ·  -n <sec> interval                                                team-03/Hawks · v1.1.0
```

</details>

## How it compares

- **`nvtop` / `nvitop`** show one machine in great detail. slurmtop shows many
  machines at once, knows about Slurm jobs, and adds the browser, Prometheus
  and report outputs.
- **DCGM exporter + Prometheus + Grafana** is the right tool for a large
  permanent installation. slurmtop is what you run *today*, on a handful of
  nodes, without installing anything — and it can feed that Grafana later.
- **`squeue`** tells you what is queued; slurmtop also tells you whether the
  GPUs a job was given are actually doing anything.

## Safety

- It only reads: `nvidia-smi`, `/proc`, `/sys`, `df`, `netstat`, `squeue`,
  `sinfo`, `scontrol`. Nothing is written on the nodes.
- Job and user names come from other people. They are stripped of terminal
  control characters, and the web page only ever inserts them as text.
- `--web` listens on `127.0.0.1` and has no login. Reach it through an SSH
  tunnel, or put it behind a proxy that authenticates — see the manual.

## Credits

Built by **team-03 / Hawks** during [HiPAC 2026](https://www.nchc.org.tw/) at
NCHC, because `watch nvidia-smi` in a separate tmux pane per node got old fast.
Issues and pull requests welcome.

<img src="qr.png" width="140" alt="QR code for this repository">

## License

MIT
