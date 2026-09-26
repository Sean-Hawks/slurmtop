# slurmtop 使用手冊

[English](MANUAL.md) · [回到 README](../README.zh-TW.md)

slurmtop 顯示一台機器或整個叢集的 CPU、記憶體、磁碟、網路和 GPU 使用狀況，告訴你每張 GPU 是誰佔著，
並列出 Slurm 佇列。你可以在終端機、瀏覽器、Grafana 裡看，也可以輸出 JSON，或錄成效能報告。

## 目錄

1. [安裝](#1-安裝)
2. [第一次使用](#2-第一次使用)
3. [看懂終端機畫面](#3-看懂終端機畫面)
4. [job、擁有者與閒置的 GPU](#4-job擁有者與閒置的-gpu)
5. [瀏覽器儀表板](#5-瀏覽器儀表板)
6. [Prometheus 與 Grafana](#6-prometheus-與-grafana)
7. [JSON 輸出](#7-json-輸出)
8. [效能報告](#8-效能報告)
9. [所有參數](#9-所有參數)
10. [各平台說明](#10-各平台說明)
11. [疑難排解](#11-疑難排解)
12. [安全性](#12-安全性)
13. [常見問題](#13-常見問題)

---

## 1. 安裝

slurmtop 就是一個檔案。執行它的那台機器需要 **Python 3.8 以上**，其他什麼都不用，也不用 pip 裝套件。

### Linux 與 macOS

```bash
curl -fsSL https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.sh | bash
```

安裝程式會放到 `/usr/local/bin`（能寫入或有免密碼 `sudo` 時），不然放到 `~/.local/bin`，
需要時會告訴你怎麼把它加進 `PATH`。想自己指定目錄：

```bash
curl -fsSL https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.sh | bash -s -- ~/bin
```

或直接手動放一個檔案——安裝程式做的也就是這件事：

```bash
curl -fsSLo ~/bin/slurmtop https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/slurmtop
chmod +x ~/bin/slurmtop
```

### Windows

先從 python.org 或 Microsoft Store 安裝 Python 3.8 以上，然後在 PowerShell 裡：

```powershell
irm https://raw.githubusercontent.com/Sean-Hawks/slurmtop/main/install.ps1 | iex
```

它會把 `slurmtop.py` 和啟動用的 `slurmtop.cmd` 放到 `%LOCALAPPDATA%\slurmtop`，並印出把這個資料夾加進
`PATH` 的指令（它自己不會改任何設定）。也可以不用安裝程式，直接在存放的地方執行 `py slurmtop.py`。

### 不能上網的叢集

在自己的電腦下載，再複製過去：

```bash
scp slurmtop 登入節點:~/bin/
```

只有你執行 slurmtop 的那台需要這個檔案；其他節點透過 SSH 讀取，不會在上面安裝任何東西。

### 移除

刪掉那個檔案就好（`rm "$(command -v slurmtop)"`；Windows 刪掉 `%LOCALAPPDATA%\slurmtop` 資料夾）。
除非你用 `--log` 或 `--html` 要求，slurmtop 不會產生其他檔案。

---

## 2. 第一次使用

### 只看這台

```bash
slurmtop --nodes localhost
```

不需要 SSH，也不需要 Slurm。Linux、macOS、FreeBSD、Windows 的筆電或工作站都能用。

### Slurm 叢集

```bash
slurmtop
```

節點清單從 `sinfo` 來。你所在的節點直接讀，其他的走 SSH；佇列從 `squeue` 讀。

### 自己列出機器

```bash
slurmtop --nodes gpu01,gpu02,gpu03
slurmtop --ssh-config                 # ~/.ssh/config 裡的每一個 Host
slurmtop --ssh-config ~/.ssh/lab.conf --nodes 另一台
```

`--ssh-config` 會用檔案裡每一個 `Host` 名稱，但略過含 `*`、`?`、`!` 的規則和 `Match` 區塊，也不展開 `Include`。
因為 slurmtop 就是執行 `ssh <名稱>`，所以 Host 別名照樣能用。

### SSH 的條件

每一台遠端節點都要能**不問密碼**就執行 `ssh <節點> true`（`ssh-agent` 裡有金鑰，或金鑰沒有密碼）。
slurmtop 用 `BatchMode=yes`，所以不會停下來等你輸入。它也會用 ControlMaster 對每台節點重複使用同一條連線
（Windows 的 OpenSSH 不支援，所以 Windows 上沒有），每次刷新每台只來回一次。

遠端只需要 POSIX `sh`：有 bash 就用 bash，沒有也可以。登入 shell 是 bash、zsh、fish 或 csh 都沒關係。

### 離開

按 Ctrl-C。終端機畫面是用備用畫面顯示的，離開後原本的內容會回來。

---

## 3. 看懂終端機畫面

```
◤ SLURMTOP // lab-h200 ──────────────────────────────────────────── 12:42:45 ◥   ← 標題（Slurm 叢集名稱或主機名稱）和時間
  ▁▂▄▅▆▇█▁▁▁▁▁▁▁▁    CORE  20/32 online                                          ← 忙碌的 GPU／全部 GPU
  46.2% UTIL         PWR 11.57 kW   MEM 1908/4493 GiB   THRM 80°C  ▲ THERMAL      ← 總功耗、GPU 記憶體、最高溫
  · ▄▄▄▄▄▄▄▄▄▄▄▄     GRID  ▉▉▉▉▉▉▉▉  │  ▉▉▉▉▉▉▉▉  │  ▉▉▉▉▁▁▁▁                   ← 每張 GPU 一格，依節點分組
  ⚠ gpu02 G5 過熱 80°C · gpu04 G0,G1 佔著卻閒置 (4103 chen)                        ← 警示列（有問題時才出現）
╭┤ LOAD // last 30 samples ├───────────────────────────────────────────────╮     ← 整個叢集 GPU 使用率的走勢
╭┤ NODE gpu01 ◉ 本機 ├───────── 8/8 忙 · 853G · 4.7 kW · 71°C ╮                  ← 每台節點一個面板
│ CPU ▕██░░░░░░░░░░░░▏  14.8% ▲ ▁▂▃▂▁▂▃▄ load 20 30 28          │
│ MEM ▕█████░░░░░░░░░▏  33.9%   684/2015 GiB                     │
│ DSK ▕██████░░░░░░░░▏  42.9%   738G/1.7T   NET ↓ 582M/s ↑ 56.4M/s
│ G0 ▕████████░░░░▏  67% ▁▂▄▆█▆▄▂  85.6G 59°  488W 4101 hawks    │  ← GPU：長條、%、歷史、記憶體、溫度、功耗、job、使用者
╰─────────────────────────────────────────────────────────────────╯
╭┤ Slurm 佇列 ├─────────────────────────────────────────────────────╮
│      JOB  名稱        使用者   狀態    已跑      進度     剩餘   節  CPU  GPU  位置
│     4101  llama-ft    hawks    ● 執行  5h12m     ██░░░░░░ 18h48m  2  256    8  gpu[01-02]
```

### 顏色與符號

| 看到 | 意思 |
|---|---|
| `▕███░░░▏` | 長條，數值越高顏色從綠變黃再變紅 |
| 數值後面的 `▁▂▃▅▇` | 最近幾次取樣的走勢 |
| `▲`／`▼` | 跟前幾次比在上升或下降 |
| 左上角的拱形儀表 | 整個叢集的 GPU 使用率（沒有 GPU 的叢集改顯示 CPU） |
| 節點旁的 `◉` | 節點狀態燈，顏色跟著負載 |
| 節點面板的底色 | 這台很忙：45% 起琥珀色、75% 起橘色、90% 起紅色 |
| 欄位顯示 `-` | 讀不到這個值（例如開了 MIG 時 nvidia-smi 回報 `[N/A]`） |
| 節點標題的 `12 秒前的資料` | 這台這次沒在期限內回應，顯示的是上一筆（見下面） |
| GPU 那行的 `閒置`／`IDLE` | 有 job 佔著這張卡卻沒在用（見[第 4 節](#4-job擁有者與閒置的-gpu)） |
| GPU 那行最後的 `4101 hawks` | 佔著這張卡的 job 和提交的人；`4101+1` 表示有兩個 job |
| GPU 那行最後的 `(root)` | 不是 Slurm 起的行程，括號裡是行程的擁有者 |
| GPU 那行最後的 `Apple M3 10-core` | 沒有人佔用時顯示卡的型號 |
| `◆ FULL LOAD` | 叢集平均使用率達 90% 以上 |
| `▲ THERMAL` | 最熱的一張卡達 78°C 以上 |

![節點面板依負載上色](../zone.png)

### 警示列

依嚴重程度列出：連不上的節點、78°C 以上的 GPU、用到 90% 以上的根目錄磁碟、資料過時的節點、佔著卻閒置的 GPU。
放不下的收成「還有 N 項」。一切正常時，這一行完全不會出現。

### 慢或卡住的節點

每次刷新，每台節點最多等 `--node-timeout` 秒（預設 6 秒，`--once` 時 20 秒）。沒在期限內回應的節點會繼續顯示上一筆資料，
並標示「N 秒前的資料」，其他節點照常更新。超過 60 秒都拿不到新資料才改顯示連不上。
卡住的取樣還在跑時不會重開新的，所以一台卡住的節點不會越積越多 SSH 連線。

### 佇列

| 欄位 | 意思 |
|---|---|
| JOB／名稱／使用者 | Slurm job 編號（陣列 job 顯示 `1006_3`）、名稱、提交的人 |
| 狀態 | `● 執行`、`◌ 排隊`，或 Slurm 的狀態代碼 |
| 已跑／剩餘 | 已經跑多久、離時間上限還剩多久 |
| 進度 | 已用掉時間上限的比例，快到時變紅 |
| 節／CPU／GPU | 要求的節點數、CPU 數、GPU 數 |
| 位置 | 執行中的 job 在哪些節點；排隊中的 job 顯示原因 |

job 下面每台節點一行，是 Slurm 看到的狀態：節點狀態、已分配的 CPU、閒置 CPU、可用記憶體。
佇列很長時，只要能省高度就會自動分成兩欄或三欄。沒有 Slurm 的機器不顯示佇列；
有裝 Slurm 但 `squeue` 沒回應時，佇列會寫「squeue 沒有回應」。

### 版面選項

- 預設什麼都不藏：畫面可以比視窗高，多出來的高度給 LOAD 走勢圖。
- `--fit` 硬塞進一個畫面，依序放棄：sparkline → 每張卡的明細（每台只留一行摘要）→ 佇列改多欄 → 最後才截掉尾端的 job。
- `--dense` 每台節點一行。節點面板高度超過「畫面高度減 12 行」時會自動切換。
- `--stack` 讓節點面板上下排列。
- `--proc` 列出每台節點最多 8 個 GPU 行程（pid、記憶體、名稱）。
- `--me` 只留你自己的 job 和 GPU（頂端的總覽仍然是整個叢集）。

### 動畫、字型與顏色

- 預設畫面只在資料變動時才變。`--flair` 打開全部特效：邊框跑光、長條的掃描光點、呼吸和閃爍的警示、
  高溫 GPU 旁的熱氣（`≋ ≈ ~`）、轉動的 job 標記和開機動畫。`--no-splash` 只關掉開機動畫。
- `--no-color` 輸出純文字；`--ascii` 用 ASCII 畫長條和走勢，給沒有方塊字的字型用。
- 輸出編碼連框線都畫不出來時（Windows 主控台導向到檔案、`LANG=C`），整個畫面會自動改用 ASCII。
- `--lang zh` 切換成繁體中文；`LANG` 是 `zh_TW`、`zh_HK`、`zh_CN` 時預設就是中文。
- `--qr` 印出專案網址的 QR code，`--qr-panel` 把它放在佇列旁邊。

---

## 4. job、擁有者與閒置的 GPU

slurmtop 綜合兩個來源，所以就算卡上沒有任何行程，也知道這張卡屬於誰：

1. 在每台節點上，對 nvidia-smi 回報的每個行程讀 `/proc/<pid>/cgroup`，從裡面找出 `job_<id>`
   （cgroup v1、v2 都可以）。不是 Slurm 起的行程會顯示它的擁有者。
2. 在執行 slurmtop 的那台，用 `scontrol -d -o show job` 看每個執行中的 job 在每台節點分到哪幾張卡，
   例如 `GRES=gpu:h200:4(IDX:0-3)`。

**佔著卻閒置**：有 job 佔著一張卡，而且連續 `--idle-samples` 次新鮮取樣的使用率都低於 5%
（預設 30 次，在預設 2 秒間隔下約一分鐘），就會標示出來。卡被用起來、換了 job、讀不到、或節點資料過時，都會重新計數。
想更早抓到可以把次數調低：

```bash
slurmtop --idle-samples 10
```

AMD 和 Jetson 的卡只靠 Slurm 的分配紀錄（第 2 個來源）判斷擁有者。

---

## 5. 瀏覽器儀表板

```bash
slurmtop --web                 # 聽 127.0.0.1:8765
slurmtop --web 9000            # 換一個埠
slurmtop --web 0.0.0.0:8765    # 所有網路介面——請先看下面的「對外開放」
```

頁面上有：
- 叢集總覽、警示列表、叢集使用率走勢圖
- 每台節點一張卡片：CPU、記憶體、磁碟、網路，以及每張 GPU 的長條與走勢、記憶體、溫度、功耗、擁有者和 `閒置` 標記
- 最下面是佇列

頁面會照 `-n` 的間隔自動更新，跟著瀏覽器切換深色／淺色，手機也能看。它完全不從網路載入任何東西。

### 從自己的電腦看

在登入節點上執行 slurmtop，然後在自己的電腦開一條 SSH 通道：

```bash
ssh -N -L 8765:localhost:8765 登入節點
# 再用瀏覽器開 http://localhost:8765
```

slurmtop 啟動時也會印出這行指令。

### 讓它一直開著

用 systemd 的使用者服務就夠了：

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
loginctl enable-linger "$USER"     # 登出後繼續執行（如果系統允許）
```

### 對外開放

儀表板**沒有登入機制**：連得到這個埠的人都看得到節點名稱、job 名稱和使用者名稱。
聽的位址不是本機時，slurmtop 會印出警告。要分享給別人，請放在會驗證身分的網頁伺服器後面，
例如 nginx 加上 basic auth：

```nginx
location /slurmtop/ {
    auth_basic "slurmtop";
    auth_basic_user_file /etc/nginx/slurmtop.htpasswd;
    proxy_pass http://127.0.0.1:8765/;
    proxy_set_header Host localhost;
}
```

頁面用的都是相對網址，所以放在子路徑底下也能用。`Host localhost` 那行是必要的：只聽本機的 slurmtop
會拒絕 Host 標頭不是本機的請求，這是用來擋 DNS rebinding 攻擊的。

### 端點

| 路徑 | 內容 |
|---|---|
| `/` | 儀表板 |
| `/api/state` | 最新一次取樣的 JSON（跟 `--json` 相同，多了介面文字） |
| `/metrics` | Prometheus 格式 |
| `/healthz` | `ok` |

第一次取樣完成前，`/api/state` 和 `/metrics` 會回 503。

---

## 6. Prometheus 與 Grafana

```yaml
# prometheus.yml
scrape_configs:
  - job_name: slurmtop
    scrape_interval: 15s
    static_configs:
      - targets: ["登入節點:8765"]
```

（這需要用 `--web 0.0.0.0:8765` 執行，或透過通道、代理伺服器來抓。）

| 指標 | 標籤 | 意思 |
|---|---|---|
| `slurmtop_node_up` | node | 有回應（可能是舊資料）為 1，連不上為 0 |
| `slurmtop_node_stale_seconds` | node | 顯示的舊資料是幾秒前的 |
| `slurmtop_cpu_utilization_percent` | node | CPU 使用率 |
| `slurmtop_memory_used_bytes`、`_memory_total_bytes` | node | 記憶體 |
| `slurmtop_load1` | node | 1 分鐘平均負載 |
| `slurmtop_disk_used_bytes`、`_disk_total_bytes` | node | 根目錄磁碟 |
| `slurmtop_network_receive_bytes_per_second`、`_transmit_…` | node | 實體網卡的收／送速度 |
| `slurmtop_gpu_utilization_percent` | node, gpu, vendor | GPU 使用率 |
| `slurmtop_gpu_memory_used_bytes`、`_memory_total_bytes` | node, gpu, vendor | GPU 記憶體 |
| `slurmtop_gpu_temperature_celsius`、`slurmtop_gpu_power_watts` | node, gpu, vendor | 溫度、功耗 |
| `slurmtop_gpu_idle_held` | node, gpu, vendor | 佔著卻閒置為 1 |
| `slurmtop_gpu_owner_info` | node, gpu, vendor, job, user | 永遠是 1，用來把 GPU 和 job 對起來 |
| `slurmtop_jobs` | state | 佇列裡各狀態的 job 數 |

常用查詢：

```promql
avg(slurmtop_gpu_utilization_percent)                                    # 叢集平均
sum by (user) (slurmtop_gpu_owner_info)                                   # 每個人佔了幾張卡
sum(slurmtop_gpu_idle_held)                                               # 佔著卻閒置的卡數
slurmtop_gpu_utilization_percent * on(node, gpu) group_left(job, user) slurmtop_gpu_owner_info
```

---

## 7. JSON 輸出

```bash
slurmtop --json > sample.json
slurmtop --json | jq '.nodes[] | .name as $n | .gpus[]? | select(.idle_held) | {node: $n, gpu: .index, job, user}'
```

最上層：`version`、`time`（Unix 秒數）、`cluster`、`summary`、`nodes`、`slurm`（有沒有裝 Slurm）、
`slurm_down`、`queue`、`queue_stale_s`、`alerts`、`history`。

- `summary`：`nodes`、`nodes_up`、`gpus`、`gpus_busy`、`gpu_util`、`power_w`、`gpu_temp_max`、
  `vram_used_mib`、`vram_total_mib`、`cpu_pct`、`mem_used_mib`、`mem_total_mib`。
- 每台節點：`name`、`up`、`stale_s`、`local`、`cpu_pct`、`load`、`cpus`、`mem_used_mib`、`mem_total_mib`、
  `disk {pct, used, total}`、`net {rx, tx}`（bytes/s，第一次取樣時是 `null`）、`gpus`、`history`。
- 每張 GPU：`index`、`uuid`、`vendor`（`nvidia`、`amd`、`apple`、`jetson`）、`model`、`util`、`mem_used_mib`、
  `mem_total_mib`、`temp_c`、`power_w`、`job`、`user`、`idle_held`、`history`。
- 佇列裡的每個 job：`id`、`job_id`（真正的編號，陣列 job 會跟 `id` 不同）、`name`、`state`、`user`、
  `elapsed`／`left`／`limit`（Slurm 原本的寫法）、`elapsed_s`／`left_s`／`limit_s`（秒數）、
  `nodes`、`cpus`、`gpus`、`gres`、`where`。

單位都是原始單位，讀不到的值是 `null`。`--me` 在這裡一樣有效。

---

## 8. 效能報告

`--report` 會錄下一段時間的取樣，最後整理成摘要。

```bash
slurmtop --report 600                             # 錄十分鐘，然後出摘要
slurmtop --report -- python train.py --epochs 3   # 錄的時間剛好等於這個指令執行的時間
slurmtop --report 600 --html run.html             # 另外存一份帶圖表的單一 HTML 報告
slurmtop --report 600 --json > run.json           # 摘要改用 JSON 輸出
slurmtop --report 600 --log run.csv               # 另外把每一筆原始取樣存成 CSV
```

包住一個指令時，slurmtop 會啟動它、一直取樣到它結束，最後以**那個指令的結束碼**離開
（被訊號 N 終止時是 128+N），所以放在腳本裡也安全。
- 按 Ctrl-C 會停止錄製但照樣輸出報告，被包住的指令也會一起停掉。
- `--log`、`--html` 的路徑有問題時，在任何東西開始執行之前就會回報。

### 在 Slurm job 裡

```bash
#!/bin/bash
#SBATCH --gres=gpu:4
slurmtop --nodes "$(hostname -s)" --report --html "report-$SLURM_JOB_ID.html" -- srun python train.py
```

### 數字的意思

| 欄位 | 意思 |
|---|---|
| 平均／p95／最高 | GPU 使用率的平均、第 95 百分位數、峰值 |
| 忙碌 | 使用率超過 5% 的取樣佔幾成 |
| 記憶體峰值 | GPU 記憶體用量的最高值 |
| 最高溫 | 溫度的最高值 |
| 平均功耗 | 功耗的平均 |
| 耗電 | 功耗對時間積分（梯形法；超過 2.5 個取樣間隔的空檔不補） |
| 佔著閒置 | 這張卡被標成佔著卻閒置的時間 |
| JOB | 錄製期間在這張卡上看過的 job |

每台節點列出 CPU 平均、CPU 最高和記憶體峰值；最下面是叢集 GPU 平均和 GPU 總耗電。
過時（stale）的資料不會算進任何數字。

### HTML 報告

`--html 檔名` 會寫出一個自給自足的網頁：摘要數字、叢集使用率走勢圖、每台節點一張圖（每張 GPU 一條線），
以及上面的表格。圖是寫報告時就畫好的 SVG，所以這個檔案不需要 JavaScript，也不用連網路。
可以直接寄出去、附在工單上，或放進版本庫保存。

### CSV 紀錄

`--log 檔名` 每次取樣時附加：每台節點一行、每張 GPU 一行。終端機畫面、`--web`、`--report` 都能用；
只有在新檔案時才寫標題列。

`time, node, kind (node|gpu), gpu, vendor, util_pct, mem_used_mib, mem_total_mib, temp_c, power_w,
job, user, idle_held, disk_pct, net_rx_bps, net_tx_bps`

`kind=node` 那幾行的 `util_pct` 是 CPU 使用率。例如只用 Python 標準函式庫，算每個人的平均 GPU 使用率：

```python
import csv, collections
use = collections.defaultdict(list)
for r in csv.DictReader(open("run.csv")):
    if r["kind"] == "gpu" and r["user"] and r["util_pct"]:
        use[r["user"]].append(float(r["util_pct"]))
for user, v in sorted(use.items()):
    print(f"{user:10} {sum(v) / len(v):5.1f}%  共 {len(v)} 筆 GPU 取樣")
```

---

## 9. 所有參數

| 參數 | 預設 | 作用 |
|---|---|---|
| `-n 秒`、`--interval 秒` | 2 | 刷新間隔 |
| `--once` | | 印一個畫面就結束 |
| `--web [位址:]埠` | 127.0.0.1:8765 | 瀏覽器儀表板、`/api/state`、`/metrics` |
| `--json` | | 印一次取樣的 JSON 就結束 |
| `--report [秒]` | | 錄指定秒數，或 `--` 後面指令的執行期間，然後出摘要 |
| `--html 檔名` | | 搭配 `--report`：另存 HTML 報告 |
| `--log 檔名` | | 每次取樣附加到 CSV |
| `--nodes A,B,C` | 從 Slurm 找 | 要看哪些機器（`localhost` = 這台，不走 SSH） |
| `--ssh-config [路徑]` | ~/.ssh/config | 加入 ssh 設定檔裡的每個 Host |
| `--title 文字` | 叢集名稱／主機名稱 | 標題 |
| `--me` | | 只看自己的 job 和佔用的卡 |
| `--idle-samples N` | 30 | 連續幾次低於 5% 才標成佔著卻閒置 |
| `--node-timeout 秒` | 6（`--once` 時 20） | 每次刷新每台節點最多等多久 |
| `--proc` | | 列出 GPU 行程 |
| `--stack` | | 節點面板上下排列 |
| `--dense` | 自動 | 每台一行 |
| `--fit` | | 塞進一個畫面 |
| `--no-color` | | 純文字 |
| `--ascii` | 需要時自動 | ASCII 長條 |
| `--flair` | | 動畫和開機動畫 |
| `--no-splash` | | 搭配 `--flair`，不播開機動畫 |
| `--lang en\|zh` | 依 `LANG` | 介面語言 |
| `--qr`、`--qr-wide`、`--qr-panel` | | 專案網址的 QR code |
| `-V`、`--version` | | 顯示版本 |

---

## 10. 各平台說明

**Linux。**
- CPU 讀 `/proc/stat`，記憶體讀 `free`，磁碟讀 `df /`，網路讀 `/proc/net/dev`。
- 網路只算實體網卡：不算 `lo`、容器和 bridge 介面、VPN 通道、bond 的成員和 VLAN／IPoIB 子介面，避免同一份流量被算好幾次。
- GPU：NVIDIA 用 `nvidia-smi`；AMD 直接讀 amdgpu 驅動的 sysfs（使用率、VRAM、溫度、功耗），不用裝 ROCm 工具；
  NVIDIA Jetson 從 sysfs 讀 GPU 負載和溫度，記憶體跟 CPU 共用。Intel GPU 目前還不支援。

**macOS。**
- CPU 讀 `top`，記憶體讀 `vm_stat`，網路讀 `netstat -ib`。
- 磁碟讀資料卷（`/System/Volumes/Data`），因為 `/` 是唯讀的系統卷。
- GPU 用 `ioreg` 讀，不需要 sudo：Apple Silicon 讀得到使用率和統一記憶體用量；Intel Mac 讀得到內顯和 AMD 獨顯（含溫度、功耗）。
  Apple Silicon 的溫度和功耗需要 `sudo powermetrics`，所以顯示 `-`。

**FreeBSD。** CPU 讀 `kern.cp_time`，記憶體讀 `vm.stats`，網路讀 `netstat -ibn`（欄位位置依標題列判斷）。

**Windows。**
- 本機透過 Win32 API 讀 CPU、記憶體，`shutil.disk_usage` 讀系統磁碟，`netstat -e` 讀網路，`nvidia-smi.exe` 讀 NVIDIA 顯卡。
- 遠端 Linux 節點用內建的 OpenSSH 用戶端讀。
- Windows Terminal 和傳統主控台都能用，顏色會自動開啟。

---

## 11. 疑難排解

**節點顯示「連不上」。**
- 在同一台機器試 `ssh -o BatchMode=yes <節點> true`。會問密碼或失敗的話，先把 SSH 弄好（金鑰、`known_hosts`）。
- 再確認節點在非互動模式的 `PATH` 裡找得到 `sh` 和 `nvidia-smi`：`ssh <節點> 'command -v nvidia-smi'`。

**節點一直顯示「N 秒前的資料」。** 它有回應，只是比 `--node-timeout` 還慢。持久模式沒開時 nvidia-smi 可能很慢
（`sudo nvidia-smi -pm 1`）；也可以把期限調長：`--node-timeout 15`。

**GPU 的數值顯示「-」。** nvidia-smi 回報 `[N/A]`。開了 MIG 時的使用率、某些卡的功耗本來就是這樣。

**沒有顯示任何 GPU。** 在那台節點執行 `nvidia-smi` 看看；AMD 卡則確認 `/sys/class/drm/card*/device/gpu_busy_percent` 存在。
沒有 GPU 的節點會以只有 CPU 的方式顯示，頂端的主儀表也會改顯示 CPU。

**卡很忙，但擁有者是空的。** 可能是 Slurm 以外的行程（會顯示成 `(使用者)`），或 `/proc` 以 `hidepid` 掛載，看不到別人的行程。
有 Slurm 分配紀錄的卡仍然判斷得出來。

**長條變成方框或問號。** 你的字型沒有方塊字，請用 `--ascii`。

**Windows 上出現 `←[H` 之類的亂碼。** 你用的是很舊、不支援 VT 的主控台。請改用 Windows Terminal，或用 `--once --no-color`。

**瀏覽器顯示「forbidden host」。** 只聽本機的 slurmtop 會拒絕 Host 標頭不是本機的請求。放在代理伺服器後面時，
請加上 `proxy_set_header Host localhost;`。

**「cannot serve on …: Address already in use」。** 這個埠被別的程式佔了，換一個：`--web 8799`。

**佇列寫「squeue 沒有回應」。** Slurm 控制器太慢或當掉了。slurmtop 會把上一次的佇列保留最多一分鐘，並標示為舊資料。

---

## 12. 安全性

- slurmtop 只讀不寫。在節點上執行的是一小段唯讀的 shell 腳本（`nvidia-smi`、`/proc`、`/sys`、`df`、`netstat`）；
  只有你用 `--log`、`--html` 要求時才會寫檔案。
- job 名稱、使用者名稱、行程名稱都是別人取的。畫出來之前會先去掉控制字元，所以 job 名稱沒辦法移動你的游標、
  改你的視窗標題或寫進你的剪貼簿。
- 瀏覽器頁面一律把這些資料當純文字放進去，送出嚴格的 Content-Security-Policy、沒有內嵌腳本，
  只聽本機時還會拒絕 Host 標頭不是本機的請求。
- `--web` 沒有身分驗證：請留在本機、用 SSH 通道連過來，或在前面放一個會驗證身分的代理伺服器。

---

## 13. 常見問題

**需要 root 嗎？** 不需要。它讀的東西一般使用者都讀得到。

**會增加節點的負擔嗎？** 每次刷新，每台節點透過現有的 SSH 連線跑一小段 shell 腳本而已。機器非常多時可以用 `-n 5` 或更長的間隔。

**重新啟動後歷史還在嗎？** 即時的歷史存在記憶體裡。要永久保存，請用 `--log` 或 Prometheus。

**網頁儀表板可以好幾個人同時看嗎？** 可以。開幾個瀏覽器都行，大家共用同一份取樣。

**有鍵盤操作嗎？** 目前還沒有，用參數控制，Ctrl-C 離開。

**怎麼參與開發？**
- 測試只用標準函式庫：`python3 -m unittest discover -s tests -t .`。
- 各種工具的輸出都錄在 `tests/fixtures/`，所以不需要 GPU 和 Slurm 也能測。
- 開發紀錄在 `NIGHT_LOG.md`。
