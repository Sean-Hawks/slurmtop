# 夜間工作紀錄：overnight/v1.1

分支 `overnight/v1.1`（從 `main` 的 `9c669be` 開出來），全部工作都在這個分支上，
沒有 push、沒有開 PR、沒有動 remote、沒有發佈。第 0～3 步全部做完，
另外順手修了幾個做的過程中發現的 bug（見〈額外修掉的 bug〉）。

- 測試：`python3 -m unittest discover -s tests -t .`（純 unittest，無第三方套件）
- 最後一次完整測試結果：見文末〈最後一次完整測試〉
- **需在叢集上實測** 的項目集中列在〈需在叢集上實測〉，每項都附指令

## Commit 一覽（由舊到新）

- `7ac395b` Keep --no-color output free of escape codes
- `b26ad82` Add a fixture layer and golden-frame tests
- `5f19624` Record history once per refresh, not once per drawn frame
- `9c6e742` Survive [N/A] and empty nvidia-smi fields
- `a4ab8a0` Keep refreshing when one node hangs
- `f65d004` Read GPU counts from every squeue %b format
- `b521d1b` Add a USER column to the queue
- `cc227c3` Translate the --proc overflow line
- `d5f00c2` Align the sinfo resource rows in colour mode
- `b80c15c` Measure wide characters with unicodedata.east_asian_width
- `e170ad0` Hold still by default; move the effects behind --flair
- `798fa70` Show which job holds each GPU, flag held-but-idle GPUs, add --me
- `34f13df` Add --ssh-config to watch the hosts in an ssh config file
- `f9408c0` Show root disk usage and network throughput per node
- `0c33ed9` Collect every machine that needs attention in one alert line
- `b0882be` Add a dense one-line-per-node view for larger fleets
- `b992dee` Measure each node's deadline from when its fetch started
- `d854fa4` Ignore nvidia-smi messages and keep the last queue when squeue fails
- `8f663ec` Reap child processes on SIGTERM and SIGHUP
- `0b904b8` Do not double-count bonded, bridged or VLAN interfaces in NET
- `9a22d46` Give --once 20 seconds per node by default
- `bcc8d65` Mark the queue as stale when squeue did not answer
- `1d901e4` Fix continuation indent in the --fit render call
- （最後一個 commit 是這份 NIGHT_LOG.md 本身）

## 做完了什麼、怎麼驗證的

每一項都有對應的測試；「驗證」欄寫的是測試檔和測試類別。修 bug 的測試都確認過
**在舊程式碼上會失敗、修完才通過**（用 `git stash push slurmtop` 把程式換回舊版跑一次）。

### 第 0 步：測試基礎建設

| 項目 | 做法 | 驗證 |
|---|---|---|
| 假資料層 | `SLURMTOP_FIXTURES=<目錄>` 時 `sh()` 讀 `<目錄>/<key>.txt`，`run_script()` 讀 `node/<節點>.txt`；`node/<節點>.<k>.txt` 是第 k 次呼叫（算 CPU%、網速要兩筆），`node/<節點>.hang` 模擬卡住 | `test_infra.FixtureLayer`（含「假資料模式下完全不呼叫 subprocess」） |
| REMOTE 輸出改成具名段落 | `@@cpu`、`@@gpu`… 取代依位置切的 `@@`，之後加段不會錯位，假資料也好讀 | `test_infra.FixtureLayer.test_sections` |
| 情境 | `tests/fixtures/make_fixtures.py` 產生：`idle2x8`、`full2x8`、`na_fields`（MIG／功耗 [N/A]／空欄位）、`hang`、`unreachable`、`nogpu`、`gres`（三種 %b 格式）、`longq`（60 個 job）、`seq`、`idleheld`、`alerts`、`many`（16 台） | 改 REMOTE 格式時改產生器再重跑 |
| 固定時鐘與動畫 | `SLURMTOP_FAKE_NOW`、`SLURMTOP_FAKE_TICK`；邊框跑光原本用 `hash()`，每次執行結果不同，改成穩定的算法 | `test_infra.Reproducible`（兩個不同 PYTHONHASHSEED 畫出一樣的畫面） |
| Golden frame | `--once --no-color` + 固定 `COLUMNS/LINES`，存在 `tests/golden/`，共 20 個畫面。有意改畫面時用 `SLURMTOP_UPDATE_GOLDEN=1 python3 -m unittest tests.test_golden` 重產，再看 `git diff` | `test_golden.GoldenFrames` |
| 彩色 = 純文字 | 每個 golden 情境再跑一次彩色版，扣掉色碼後必須和 `--no-color` 一字不差（抓色碼造成的對齊錯誤，第 7 個 bug 就是它抓到的） | `test_golden.test_color_matches_plain`、`test_plain_has_no_escape_codes` |
| Python 3.8 相容 | 這台沒有 3.8（見〈取捨〉），用 `ast.parse(feature_version=(3, 8))` 檢查語法，再掃 3.9+ 才有的 API、確認只 import 標準函式庫、沒有相對 import（維持單一檔案） | `test_compat`；另外整套測試在 macOS 內建的 **Python 3.9.6** 和 Homebrew **3.14** 都跑過 |
| 本機實跑 | `./slurmtop --once --nodes localhost` 在這台 Mac 上能跑（不用假資料） | `test_infra.LocalSmoke`，也手動跑過 live 模式 |

### 第 1 步：修 bug

| # | 問題 | 修法 | 驗證 |
|---|---|---|---|
| 1 | 歷史在繪圖時寫入，一次刷新寫好幾筆 | 只在 `update_state()`／`update_history()` 寫，每次刷新一次；繪圖一律經 `hist()` 唯讀（用 `.get`，defaultdict 不會在畫圖時長出新 key） | `test_fixes.HistoryOncePerRefresh`（含深拷貝前後比對 `_hist` 不變） |
| 2 | `[N/A]`／空值讓 `float()` 掛掉 | `num()` 讀不到回傳 None；GPU/行程解析成 dict；顯示同寬的 `-`；彙總跳過 None；整台都讀不到時顯示 `-` 而不是 0% | `test_fixes.RobustGpuFields`、golden `na_fields` |
| 3 | 一台卡住整個畫面凍結 | 每台（和 Slurm 查詢）各一個 thread；每台的截止時間從**它自己開始取樣**時算（`--node-timeout`，live 預設 6 秒、`--once` 預設 20 秒）；逾時或失敗就沿用上一筆並在標題標 `stale Ns`，舊到 60 秒以上改顯示連不上；還沒跑完的取樣不重開；子行程開在獨立 process group，逾時和程式結束時整組砍掉 | `test_fixes.HungNodeDoesNotFreeze`（含真的在 PATH 放一個會卡住的假 `ssh`，確認 `--once` 準時結束而且卡住的行程被砍掉；以及「卡住的節點不會拖慢之後的刷新」） |
| 4 | %b 只認 `gres:gpu:N` | `gpu_count()` 認 `gres:gpu:N`、`gres/gpu:N`、`gres/gpu:型號:N`、`(IDX:…)`、逗號串接多種 gres | `test_fixes.GresFormats`、golden `gres` |
| 5 | 佇列沒有 USER | squeue 加 `%u`，單欄／多欄都有 | `test_fixes.UserColumn` |
| 6 | 「…還有 N 個」寫死中文 | 走 STRINGS | `test_fixes.ProcOverflowString`（另檢查 en/zh 的 key 完全一致） |
| 7 | sinfo 那行 `bold(n):<10` 錯位 | 改用 `pad()` | `test_golden.test_color_matches_plain`（修之前標成 expectedFailure，修完拿掉） |
| 8 | 寬字判斷寫死區間 | `unicodedata.east_asian_width` 是 W/F 算兩格 | `test_fixes.WideChars`（emoji、CJK 擴充 B） |
| 9 | 動畫預設全開 | 邊框跑光、掃描光點、閃爍、熱氣、開機動畫預設關；`--flair` 一次全開；QR 面板改 `--qr-panel`；`--qr` 保留；舊的 `--no-qr` 留著當隱藏的空參數；README 同步 | `test_fixes.CalmByDefault`（沒有 `--flair` 時換 tick 畫面逐位元相同） |

### 第 2 步：GPU ↔ job 對應（**需在叢集上實測**）

- REMOTE 的 `nvidia-smi` 多要 `uuid`（每張卡）和 `gpu_uuid`（每個行程），新的 `@@jobs` 段對每個 pid 讀
  `/proc/<pid>/cgroup` 抓 `job_<id>`，並回報行程擁有者（`stat -c %U`，失敗退回 `ps -o user=`）。
- 另外加了一個規格外的補強：在控制端解析 `scontrol -d -o show job` 的 `GRES=gpu:…(IDX:0-3)`。
  只靠 pid 的話，**分到卡卻完全沒有行程**的 job 看不到，而那正是「佔著卻閒置」最典型的情況。
- 每張卡那一行最後顯示 `871 hawks`；不是 Slurm 起的行程顯示 `(root)`；陣列 job 用 `%i`（`1006_3`）顯示、用 `%A` 對 cgroup。
- 「佔著卻閒置」：有 job 佔著且連續 `--idle-samples` 次（預設 30，約一分鐘）新鮮取樣都 < 5%，
  該列標 `IDLE`、頂端警示列列出。換 job、用起來、讀不到、沿用舊資料都會重新計數。
- `--me`：只留自己的 job 和自己佔用（job 是自己的，或卡上有自己的行程）的 GPU。
- 驗證：`test_jobs`——把 `/proc` 換成假目錄樹，**真的用 bash 跑 REMOTE 的 jobs 段**（cgroup v1、v2、非 Slurm 行程、已結束的 pid）；
  `parse_alloc`（新舊兩種 GRES 寫法、多批節點、多種型號、PENDING 不算）；閒置計數的各種規則；`--me` 三種使用者；golden `idleheld`、`idleheld_me`。

### 第 3 步：擴大到一般伺服器（四項都做了）

1. `--ssh-config [路徑]`：讀 Host（略過 `* ? !`、Match；不展開 Include），可和 `--nodes` 合併，都沒給才問 Slurm。驗證：`test_servers.SshConfig`。
2. 磁碟與網路：REMOTE 加 `@@disk`（`df -Pk`）和 `@@net`（Linux `/proc/net/dev`、macOS `netstat -ibn`），面板多一行 `DSK … NET ↓… ↑…`。
   驗證：`test_servers.DiskAndNet`——**用真的 awk 程式**跑錄下來的 `/proc/net/dev`（含介面名稱太長、冒號黏住數字的情況）和 `netstat -ibn`（含少一欄的 utun 行）；
   在這台 Mac 上 live 模式實際看到網速與 52.1% 的磁碟（和 `df` 一致）。**Linux 那段需在叢集上實測。**
3. 頂端警示列：斷線 > GPU 過熱（≥78°C，沿用原本 THERMAL 的門檻）> 磁碟 ≥90% > 資料過時 > 佔著卻閒置；放不下收成 `+N more`；沒問題不佔行。驗證：`test_servers.AlertLine`、golden `alerts`。
4. 密集檢視：`--dense`，或節點面板高度超過「畫面高度 − 12 行」（且至少兩台）時自動切換，一台一行、各欄對齊。驗證：`test_servers.DenseView`、golden `many_dense`、`full2x8_dense`。

### 額外修掉的 bug（做的過程中發現的）

- `--no-color` 時 `clip()` 還是會補 `\033[0m`，純文字輸出混進控制碼；QR 在 `--no-color` 下仍然用 24-bit 色碼畫（改用半格字元畫亮模組，並有「解回點陣跟內嵌的一樣」的測試）。
- 中文介面的佇列標題（名稱、節）用 f-string 寬度對齊，後面每一欄都歪兩格。
- QR 面板旁邊寬度不夠時，佇列仍硬擠成多欄，把欄位截斷在 LEFT／ELAPSED。
- 佇列在多欄沒有比較矮的時候也會改多欄（例如只有一個 job、但節點資源清單很長）。
- 節點很多時頂端 GRID 列超出畫面寬度。
- 第 3 個 bug 的第一版修法有個問題：卡住的節點會讓**之後每次刷新**都多等一次 timeout（live 模式實測時發現），已改成截止時間從該次取樣開始時算。

### 夜間自我審查後修掉的問題

全部做完後，另外開了一個唯讀的審查代理把整個分支的 diff 看過一遍，並用各種終端機寬度
（40／60／200 欄）× 各種參數把每個情境都畫過，沒有找到會讓畫面掛掉的輸入。
它回報的 5 個問題全部修掉，每個都有測試（同樣確認在修之前會失敗）：

| 問題 | 修法 | 驗證 |
|---|---|---|
| nvidia-smi 的訊息（"No devices were found"、驅動連不上）被當成一張 GPU，沒 GPU 的機器變成 GPU 模式 | GPU 行開頭必須是數字索引 | `test_jobs.ReviewFixes.test_nvidia_smi_messages_are_not_gpus` |
| squeue 失敗／逾時被當成「沒有 job」的新資料：佇列變空、GPU 分配紀錄被清掉、閒置計數歸零 | `sh()`／`_run()` 加 strict 模式（逾時或結束碼非 0 回傳 None）；squeue 失敗就沿用上一次的佇列，並在佇列標題標 `stale Ns`；沒裝 Slurm 時佇列照樣是空的 | `test_jobs.ReviewFixes.test_failed_squeue_keeps_last_queue_and_idle_state`（假資料層支援 `<key>.fail` 模擬指令失敗） |
| 子行程開在自己的 session 之後，關掉終端機（SIGHUP）或 SIGTERM 時卡住的 ssh 會留下來 | 收到 TERM／HUP 轉成正常結束，還原終端機並砍掉子行程 | `test_fixes.HungNodeDoesNotFreeze.test_signals_reap_children`（真的送訊號給 live 模式） |
| Linux 網速把 bond 和它的成員網卡、VLAN／IPoIB 子介面重複計算（約 2 倍） | 略過有 `/sys/class/net/<if>/master` 的網卡和名稱有 `.` 的子介面 | `test_servers.DiskAndNet.test_linux_bond_and_vlan_not_double_counted`（假的 /sys 樹） |
| `--once` 對第一次取樣只等 6 秒，單純慢的節點會被顯示成連不上（main 以前等 20 秒） | `--once` 預設等 20 秒；live 模式維持 6 秒；明確給 `--node-timeout` 時照給的值 | `test_fixes.HungNodeDoesNotFreeze.test_once_waits_longer_by_default` |

## 需在叢集上實測

這台是 macOS、沒有 nvidia-smi 和 Slurm、今晚也連不到叢集，下面這些**只用假資料驗證過**。
建議在登入節點上照順序跑（`n1`、`n2` 換成實際節點名；共用帳號下測試 job 一律用 `hawks-` 開頭命名）：

```bash
# 0. 先確認分支上的版本能跑、畫面正常（彩色、對齊、中文）
./slurmtop --once
./slurmtop --once --lang zh
./slurmtop                       # live 模式看幾次刷新，Ctrl-C 離開

# 1. nvidia-smi 新增的欄位（uuid / gpu_uuid）在這版驅動上都有
nvidia-smi --query-gpu=index,uuid,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_gpu_memory,process_name --format=csv,noheader,nounits

# 2. cgroup 裡找得到 job_<id>（v1 或 v2 都應該有）
srun -N1 --gres=gpu:1 --job-name=hawks-cgroup-test bash -c 'cat /proc/self/cgroup'
#    對一個正在跑的 GPU 行程（pid 從上面第二個指令拿）：
grep -o 'job_[0-9]*' /proc/<pid>/cgroup; stat -c %U /proc/<pid>
#    注意：若 /proc 以 hidepid=2 掛載，別人的行程讀不到，只剩 scontrol 那條路
mount | grep ' /proc '

# 3. scontrol -d -o 的一行裡真的有 Nodes=… GRES=gpu:…(IDX:…)
scontrol -d -o show job <jobid> | tr ' ' '\n' | grep -E '^(JobId|UserId|JobState|Nodes|GRES|GRES_IDX)='

# 4. Slurm 的 IDX 和 nvidia-smi 的 index 是同一套編號（最重要的一項，不一致的話 GPU 會掛錯 job）
scontrol -d show job <jobid> | grep -o 'IDX:[^)]*'
srun --jobid=<jobid> --overlap nvidia-smi --query-gpu=index,uuid --format=csv,noheader
nvidia-smi --query-gpu=index,uuid --format=csv,noheader     # 在該節點上、job 外面跑，對 uuid

# 5. 陣列 job：%A 和 cgroup 裡的 job id 相同
sbatch --array=1-2 --gres=gpu:1 --job-name=hawks-array-test --wrap 'sleep 300'
squeue -h -o '%i %A' -u $USER

# 6. 佔著卻閒置：開一個佔卡但不用的 job，約 3 次刷新（6 秒）後應該出現 IDLE 和頂端警示
srun -N1 --gres=gpu:1 --job-name=hawks-idle-test sleep 600 &
./slurmtop --idle-samples 3
./slurmtop --me
scancel -n hawks-idle-test; scancel -n hawks-array-test     # 測完收掉

# 7. 磁碟與網路（Linux 那段 awk）：面板的 DSK 要和 df 一致，NET 第二次刷新後有數字
df -Pk /
awk 'NR>2' /proc/net/dev          # 看介面名稱，確認沒有把該算的網卡（例如 ib0、bond0）排除掉
ls -d /sys/class/net/*/master     # 這些是 bond／bridge 成員，會被略過（流量算在上層那張卡）
./slurmtop -n 2

# 8. 卡住的節點：拿一個不會回應的位址當節點，其他節點要照常更新
./slurmtop --nodes n1,10.255.255.1 --node-timeout 3

# 9. 一般伺服器模式
./slurmtop --ssh-config ~/.ssh/config
./slurmtop --dense
```

另外：MIG 的 `[N/A]` 用的是依 NVIDIA 文件編的假資料；叢集上的 H200 若沒開 MIG 就測不到，屬於低風險。

## 取捨與我替你做的決定

- **commit 作者**：這台的全域 git 設定只有 `user.email=seanhawks0321@gmail.com`、沒有 `user.name`。
  為了和 repo 既有歷史一致，每個 commit 用環境變數指定成 `Sean-Hawks <gwenythshih@gmail.com>`，**沒有改任何 git 設定**，
  也沒有任何 Co-Authored-By 或 AI 工具的署名（README 裡也沒有）。想換成另一個 email 的話，合併前用
  `git rebase main --exec 'git commit --amend --no-edit --reset-author'`（先設好你要的 user.email）即可整批改掉。
- **Python 3.8**：這台只有 3.9.6（macOS 內建）和 3.14。`uv` 可以下載 3.8，但下載直譯器需要你同意，所以沒做；
  改用 3.9 實跑整套測試 + `ast` 的 3.8 語法檢查 + 掃 3.9 以後的 API。建議在叢集上用 3.8 再跑一次 `python3.8 -m unittest discover -s tests -t .`（如果有的話）。
- **`--flair` 的範圍**：你列的是邊框跑光、掃描光點、閃爍、熱氣、開機動畫；我把**呼吸／脈動**（滿載的長條、節點底色、快到時限的 job）和**轉動的 job 標記**也歸進 `--flair`，
  因為你說 `--flair`「一次打開全部動畫」。預設下畫面只在資料變動時改變（有測試保證）。
- **`--no-qr`** 沒刪，留成隱藏的空參數，免得別人腳本裡的舊指令報錯。
- **stale 規則**：ssh 失敗（沒有輸出）也當成逾時處理、沿用上一筆，取代原本的「重試一次」；舊資料最多沿用 60 秒（`STALE_MAX`）。
  `--node-timeout` 預設：live 6 秒、`--once` 20 秒（`--once` 沒有下一次刷新可以補）。Slurm 查詢也走同一套截止時間，
  squeue 失敗或逾時就沿用上一次的佇列並在標題標 `stale Ns`。
  沿用的舊資料不寫進該節點的歷史，也不算閒置取樣。
- **scontrol -d**：規格只要求 cgroup；我另外加了 `scontrol -d -o show job` 的 IDX 解析（原因見第 2 步）。兩個來源取聯集。
- **閒置門檻**：< 5%、預設連續 30 次（2 秒間隔約一分鐘）；太短會被 dataloader 的空檔誤判。讀不到使用率（MIG）不算閒置。
- **`--me`**：頂端總覽維持整個叢集（當作背景資訊），面板和佇列才篩；自己沒有佔任何卡時顯示一行說明；連不上的節點在 `--me` 下不顯示。
- **macOS 的「根目錄」**：`/` 是唯讀系統卷，永遠只顯示幾 %，所以改讀 `/System/Volumes/Data`（使用者資料所在、會滿的那個）。Linux 照規格讀 `/`。
- **網速**：只算實體網卡，排除 lo、veth、docker、br-、virbr、cni、flannel、cali、tun、tap（macOS 另排除 utun、awdl、bridge 等），避免同一份流量被算好幾次；單位以 1024 為底。
- **自動密集檢視門檻**：節點面板高度 > 畫面高度 − 12 行，且至少兩台。
- **README**：demo.gif 和文字範例是舊的預設樣子（有 QR、有動畫），我**沒有重錄**，只在說明加註「用 `--flair --qr-panel` 錄的」。重錄交給你。
- **版本號**：`__version__` 仍是 1.0.0，沒有自己升版（發佈是你的決定）。
- **沒有做**：鍵盤互動、改名（依你的指示留給你決定）。

## 沒做完的項目與建議下一步

第 0～3 步都做完了。建議接下來：

1. 照〈需在叢集上實測〉跑一輪，特別是第 4 項（IDX 對 nvidia-smi index）。
2. 若叢集的 `/proc` 有 hidepid，cgroup 那條路會失效，只剩 scontrol；可以考慮在 README 註明。
3. 重錄 demo.gif、更新 README 裡的文字範例，然後把 `__version__` 升到 1.1.0。
4. 決定鍵盤互動和改名。
5. 網速目前是「所有實體網卡加總」；如果你們比較想看 InfiniBand 本身的流量（RDMA 不經過 /proc/net/dev），
   要另外讀 `/sys/class/infiniband/*/ports/*/counters/port_{rcv,xmit}_data`，這版沒有做。

## 最後一次完整測試

2026-09-24 清晨，在這台 Mac 上，兩個直譯器各跑一次整套：

```
$ python3 -m unittest discover -s tests -t .            # Homebrew
Python 3.14.6
Ran 104 tests in 19.276s

OK

$ /usr/bin/python3 -m unittest discover -s tests -t .   # macOS 內建
Python 3.9.6
Ran 104 tests in 17.825s

OK

$ ./slurmtop --once --nodes localhost --no-color   # 不用假資料
rc=0，畫面正常（NODE localhost、DSK 52.1%）
```

共 104 個測試、20 個 golden frame。`slurmtop` 仍是單一檔案、只用標準函式庫。
