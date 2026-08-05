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
hipac-team3  ▕██████████░░░░░░▏  65.4% · ▁▁▁▁▁▁▁▁▁▆  16/16 GPUs · 1727/2246G · 9.57 kW · 60°C               02:53:06
  GPUs ▉▉▉▉▉▉▉▉  │  ▉▉▉▉▉▉▉▉
╭ n1 local ───────────── 8/8 busy · 863G · 5.3 kW · 60°C ╮╭ n2 ssh ─────────────── 8/8 busy · 864G · 4.3 kW · 51°C ╮
│ CPU ▕█░░░░░░░░░░░░░▏   3.9% · ▁▁▁▁▁▁▁▁ load 11 9 10    ││ CPU ▕█░░░░░░░░░░░░░▏   3.7% · ▁▁▁▁▁▁▁▁ load 8 10 11    │
│ RAM ▕█░░░░░░░░░░░░░▏   4.4%   88/2016 GiB              ││ RAM ▕█░░░░░░░░░░░░░▏   5.2%   104/2016 GiB             │
│ GPU0 ▕████████████▏  98% ▁▁▁▁▁▁▁█ 110.4G 60°  642W     ││ GPU0 ▕█████░░░░░░░▏  44% ▁▁▁▁▁▁▁▄ 110.5G 47°  528W     │
│ GPU1 ▕████████████▏  98% ▁▁▁▁▁▁▁█ 107.5G 58°  678W     ││ GPU1 ▕███░░░░░░░░░▏  28% ▁▁▁▁▁▁▁▃ 107.6G 50°  548W     │
│ GPU2 ▕████████████▏  98% ▁▁▁▁▁▁▁█ 107.5G 57°  676W     ││ GPU2 ▕█████░░░░░░░▏  38% ▁▁▁▁▁▁▁▄ 107.6G 48°  549W     │
│ GPU3 ▕████████████▏  98% ▁▁▁▁▁▁▁█ 107.5G 57°  659W     ││ GPU3 ▕██████░░░░░░▏  47% ▁▁▁▁▁▁▁▄ 107.6G 49°  539W     │
│ GPU4 ▕████████████▏  98% ▁▁▁▁▁▁▁█ 107.5G 58°  680W     ││ GPU4 ▕██░░░░░░░░░░▏  20% ▁▁▁▁▁▁▁▂ 107.6G 51°  533W     │
│ GPU5 ▕████████████▏  98% ▁▁▁▁▁▁▁█ 107.5G 57°  633W     ││ GPU5 ▕█░░░░░░░░░░░▏  12% ▁▁▁▁▁▁▁▂ 107.6G 48°  520W     │
│ GPU6 ▕████████████▏  98% ▁▁▁▁▁▁▁█ 107.5G 58°  651W     ││ GPU6 ▕█████░░░░░░░▏  38% ▁▁▁▁▁▁▁▄ 107.6G 48°  517W     │
│ GPU7 ▕████████████▏  98% ▁▁▁▁▁▁▁█ 107.5G 58°  677W     ││ GPU7 ▕████░░░░░░░░▏  36% ▁▁▁▁▁▁▁▄ 107.6G 47°  541W     │
╰────────────────────────────────────────────────────────╯╰────────────────────────────────────────────────────────╯
╭ Slurm queue ─────────────────────────────────────────────────────────────────────────────────────────────────────╮
│      JOB  NAME        STATE   ELAPSED   PROG     LEFT       N  CPU  GPU  WHERE                                   │
│      212  qegdr       ◌ pend  0s        ░░░░░░░░ 1h00m      2  224    8  (Resources)                             │
│      208  qe-pw-o7    ◓ run   8m51s     ███░░░░░ 16m09s     1  224    8  n2                                      │
│      211  qeucc       ◓ run   1m34s     ░░░░░░░░ 58m26s     1  224    8  n1                                      │
│ ┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈ │
│  n1 allocated CPU ▕██████████▏ 224/224 idle 0   RAM free 1481 GiB                                                │
│  n2 allocated CPU ▕██████████▏ 224/224 idle 0   RAM free 1156 GiB                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
  Ctrl-C quit  ·  --proc processes  ·  --stack vertical  ·  -n <sec> interval                 team-03/Hawks · v1.0.0
```

</details>

![node load zones](zone.png)

*The whole panel is tinted by node load: n1 pegged and hot, n2 middling, idle
nodes stay dark.*

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
slurmtop --no-splash        # skip the boot animation
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
| `▲` `▼` | trend against the last few samples |
| seven-segment readout | cluster GPU utilisation, tinted by the value |
| `◤ ◥` `┤ ├` | HUD chrome — section labels and frame ticks |
| `◉` | per-node status LED, tinted by that node's load |
| tinted panel background | the whole node zone warms up with its load — amber past 45 %, orange past 75 %, pulsing red past 90 % — so the node that is cooking is obvious without reading a single number |
| moving bright cell in a bar | scan sweep, advances every refresh |
| `≋ ≈ ~` next to a GPU | heat plume — the GPU is ≥70 °C or ≥95 % utilised |
| breathing bars | anything pegged at ≥95 % pulses; so does a job within 15 % of its time limit |
| `◆ FULL LOAD` | cluster mean utilisation ≥90 %, blinking |
| `▲ THERMAL` | hottest GPU ≥78 °C, blinking |
| LOAD panel | cluster utilisation on a sweeping scope — data is written in a circle like an EKG, the bright column is the write head, and each cell uses eighth-blocks so six rows resolve 48 levels |
| bright cell running along a border | signal trace, one per panel at different phases |
| `GPUs ▉▉▁▁▁▁▁▁ │ ▉▉▉▉▉▉▉▉` | one cell per GPU in the cluster, grouped by node — the whole fleet at a glance |
| `◓ run` / `◌ pend` | Slurm job state; the running marker spins on every refresh |
| `PROG ███░░░░░` | how much of the job's time limit is used up — turns red as it approaches the wall |
| `2h45m`, `20m00s`, `3d02h` | durations, always with units |
| header line | cluster totals: mean GPU utilisation, busy GPU count, VRAM, power draw, hottest GPU |
| panel border | tinted by that node's average GPU load |

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
