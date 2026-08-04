# slurmtop

A one-screen terminal dashboard for small GPU clusters. CPU, RAM, per-GPU
utilisation for every node, plus the Slurm queue — with gradient bars and
sparkline history, in a single 24-line frame.

Built during [HiPAC 2026](https://www.nchc.org.tw/) because `watch nvidia-smi`
on each node in a separate tmux pane got old fast.

```
mycluster  ▕███████░░░░░░░░░▏  44.1% ▁▂▃▅▇▇▅▃▂▁  9/16 GPUs · 187/2246G · 4.71 kW · 62°C   06:05:38
╭ n1 local ────────────── 8/8 busy · 58G · 2.4 kW · 62°C ╮╭ n2 ssh ──────────────── 1/8 busy · 129G · 1.3 kW · 49°C ╮
│ CPU ▕███████░░░░░░░▏  53.7% ▁▂▃▅▇▇▅▃ load 101 57 32    ││ CPU ▕█░░░░░░░░░░░░░▏   1.1% ▁▁▁▁▁▁▁▁ load 7 4 5        │
│ RAM ▕█░░░░░░░░░░░░░▏   4.8%   97/2016 GiB              ││ RAM ▕░░░░░░░░░░░░░░▏   0.6%   13/2016 GiB              │
│ GPU0 ▕████████████▏ 100% ▁▂▃▅▇▇▇█  11.6G 55°  655W     ││ GPU0 ▕████████████▏ 100% ▁▁▁▁▁▁▁█ 128.6G 49°  501W     │
│ ...                                                    ││ ...                                                    │
╰────────────────────────────────────────────────────────╯╰────────────────────────────────────────────────────────╯
╭ Slurm queue ─────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    JOB  NAME        STATE  ELAPSED   LEFT       N  CPU  GPU  WHERE                                               │
│     45  hpl-full    ◐ pend  0s        20m00s     2  224    8  (Resources)                                        │
│     33  qe          ● run   14m55s    2h45m      1  224    8  n1                                                 │
│  n1 allocated CPU ▕██████████▏ 224/224 idle 0   RAM free 1457 GiB                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Why

`nvtop` is great but shows one machine. `squeue` tells you what is queued but
not whether the GPUs are actually doing anything. On a handful of nodes you
usually want both at once, on one screen, without installing an agent, a time
series database and a web UI.

## Install

Single file, no dependencies beyond the standard library.

```bash
curl -fsSLo /usr/local/bin/slurmtop \
  https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/slurmtop
chmod +x /usr/local/bin/slurmtop
```

Requirements:

- Python 3.8+ on the machine you run it from
- `nvidia-smi` on each node
- passwordless SSH from that machine to every remote node
- Slurm (optional — used for node discovery and the queue panel; without it
  pass `--nodes` and the queue section is simply empty)

## Usage

```bash
slurmtop                    # refresh every 2s, nodes discovered from Slurm
slurmtop -n 5               # refresh every 5s
slurmtop --once             # print one frame and exit (good for chat/logs)
slurmtop --nodes a,b,c      # explicit node list, skip Slurm discovery
slurmtop --proc             # also list the processes on each GPU
slurmtop --stack            # force vertical layout
slurmtop --no-color         # plain text
slurmtop --lang zh          # 繁體中文介面（預設依 $LANG 自動判斷）
slurmtop --title "lab-gpu"  # header title (default: Slurm ClusterName)
```

Run it on any node in the cluster. The node you are on is read locally; the
rest are read over SSH, one round trip each per refresh.

## Reading the display

| Element | Meaning |
|---|---|
| `▕███░░░▏` | gradient bar, green → yellow → red |
| `▁▂▃▅▇` | sparkline of the last 24 refreshes — tells idle-but-spiky apart from steadily pegged |
| `● run` / `◐ pend` | Slurm job state |
| `2h45m`, `20m00s`, `3d02h` | durations, always with units |
| header line | cluster totals: mean GPU utilisation, busy GPU count, VRAM, power draw, hottest GPU |

The layout adapts to the terminal: sparklines need ≥118 columns, panels are
placed side by side as long as they fit, and the job list is truncated to keep
everything on one screen.

## Notes

- Reads only `nvidia-smi`, `/proc/stat`, `/proc/loadavg`, `free`, `squeue` and
  `sinfo`. Nothing is written anywhere and no daemon is installed.
- Sparkline history lives in the process, so it starts empty on each launch.
- AMD/Intel GPUs are not supported (patches welcome — the only coupling is the
  `nvidia-smi --query-gpu` call in `REMOTE`).

## License

MIT
