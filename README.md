# slurmtop

A one-screen terminal dashboard for small GPU clusters. CPU, RAM, per-GPU
utilisation for every node, plus the Slurm queue — with gradient bars and
sparkline history, in a single 24-line frame.

Built during [HiPAC 2026](https://www.nchc.org.tw/) because `watch nvidia-smi`
on each node in a separate tmux pane got old fast.

![slurmtop in action](demo.gif)

*Real capture from a 2-node / 16×H200 cluster. Watch the sparklines fill in as
jobs start and the queue drain as they finish.*

<details>
<summary>Same thing as text</summary>

```
hipac-team3  ▕█░░░░░░░░░░░░░░░▏   6.2% ▁▁▁▁▁▁▁▁▁▁  1/16 GPUs · 187/2246G · 2.40 kW · 49°C                   06:10:12
╭ n1 local ────────────── 0/8 busy · 58G · 1.1 kW · 39°C ╮╭ n2 ssh ─────────────── 1/8 busy · 129G · 1.3 kW · 49°C ╮
│ CPU ▕░░░░░░░░░░░░░░▏   0.9% ▁▁▁▁▁▁▁▁ load 8 8 8        ││ CPU ▕░░░░░░░░░░░░░░▏   0.9% ▁▁▁▁▁▁▁▁ load 6 5 6        │
│ RAM ▕░░░░░░░░░░░░░░▏   1.6%   32/2016 GiB              ││ RAM ▕░░░░░░░░░░░░░░▏   0.6%   13/2016 GiB              │
│ GPU0 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   7.3G 39°  144W     ││ GPU0 ▕████████████▏  99% ▁▁▁▁▁▁▁█ 128.6G 49°  501W     │
│ GPU1 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   7.3G 38°  143W     ││ GPU1 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   0.0G 37°  122W     │
│ GPU2 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   7.3G 38°  143W     ││ GPU2 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   0.0G 37°  127W     │
│ GPU3 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   7.3G 39°  141W     ││ GPU3 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   0.0G 37°  119W     │
│ GPU4 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   7.3G 38°  142W     ││ GPU4 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   0.0G 35°   77W     │
│ GPU5 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   7.3G 38°  140W     ││ GPU5 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   0.0G 37°  119W     │
│ GPU6 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   7.3G 39°  142W     ││ GPU6 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   0.0G 35°   77W     │
│ GPU7 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   7.3G 39°  143W     ││ GPU7 ▕░░░░░░░░░░░░▏   0% ▁▁▁▁▁▁▁▁   0.0G 37°  123W     │
╰────────────────────────────────────────────────────────╯╰────────────────────────────────────────────────────────╯
╭ Slurm queue ─────────────────────────────────────────────────────────────────────────────────────────────────────╮
│    JOB  NAME        STATE  ELAPSED   LEFT       N  CPU  GPU  WHERE                                               │
│     45  hpl-full    ◐ pend  0s        20m00s     2  224    8  (Resources)                                        │
│     48  qe          ◐ pend  0s        30m00s     1  112    8  (Nodes required for jo                             │
│     33  qe          ● run   18m32s    2h41m      1  224    8  n1                                                 │
│     47  racing-base ● run   15m49s    54m11s     1    4    1  n2                                                 │
│ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ │
│  n1 allocated CPU ▕██████████▏ 224/224 idle 0   RAM free 1457 GiB                                                │
│  n2 mixed    CPU ▕░░░░░░░░░░▏ 4/224 idle 220   RAM free 1548 GiB                                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
  Ctrl-C quit  ·  --proc processes  ·  --stack vertical  ·  -n <sec> interval
```

</details>

## Why

`nvtop` is great but shows one machine. `squeue` tells you what is queued but
not whether the GPUs are actually doing anything. On a handful of nodes you
usually want both at once, on one screen, without installing an agent, a time
series database and a web UI.

## Install

Single file, no dependencies beyond the standard library.

```bash
curl -fsSL https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.sh | bash
```

The installer picks `/usr/local/bin` when it can write there (using `sudo` if
passwordless sudo is available) and falls back to `~/.local/bin`, telling you
how to fix your `PATH` if needed. Pass a directory to choose yourself:

```bash
curl -fsSL .../install.sh | bash -s -- ~/bin
```

Or just drop the single file in place — that is all the installer does:

```bash
curl -fsSLo /usr/local/bin/slurmtop \
  https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/slurmtop
chmod +x /usr/local/bin/slurmtop
```

Only the machine you run it from needs the script — it reads the other nodes
over SSH. Installing it on every node is optional but handy.

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
slurmtop --fit              # squeeze into one screen instead of showing everything
slurmtop --no-color         # plain text
slurmtop --ascii            # ASCII bars, for fonts without block glyphs
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

By default nothing is hidden: every GPU row and every queued job is printed,
even if the result is taller than the window. If the queue is long, the job
list splits into two or three columns to claw back some height, but jobs are
never dropped.

Panels sit side by side while they fit, and sparklines need ≥118 columns.

If you would rather have a single screen that never scrolls, use `--fit`. That
mode gives up detail in order — sparklines, then per-GPU rows collapsed to one
line per node, then multi-column jobs, and finally trimming the job list with
a `N more job(s) hidden` note.

If bars and sparklines show up as blank boxes or oddly wide blocks, your font
lacks the Unicode block glyphs. Use `--ascii`:

```
hipac-team3  [#...............]   6.2% ..........  1/16 GPUs · 129/2246G · 2.16 kW · 49°C
│ CPU [..............]   0.6% load 5 6 7        ││ GPU0 [############]  99% 128.6G 49°  502W  │
```

The live view runs in the terminal's alternate screen buffer, so quitting
restores whatever was on screen before and leaves no stack of stale frames in
your scrollback.

## Notes

- Reads only `nvidia-smi`, `/proc/stat`, `/proc/loadavg`, `free`, `squeue` and
  `sinfo`. Nothing is written anywhere and no daemon is installed.
- Sparkline history lives in the process, so it starts empty on each launch.
- AMD/Intel GPUs are not supported (patches welcome — the only coupling is the
  `nvidia-smi --query-gpu` call in `REMOTE`).

## Credits

Built by **team-03 / Hawks** during HiPAC 2026 at NCHC.
Issues and pull requests welcome.

## License

MIT
