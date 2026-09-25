#!/usr/bin/env python3
"""產生 tests/fixtures/ 底下的假資料。

每個子目錄是一個情境，內容就是 slurmtop 在叢集上會拿到的原始輸出
（REMOTE 腳本、squeue、sinfo、scontrol）。數值依照 2 台 x 8 張 H200 的
實際樣子編的；改了 REMOTE 的輸出格式就改這裡再重跑一次：

    python3 tests/fixtures/make_fixtures.py
"""

import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))

H200_MIB = 143771
SQUEUE_FMT = "%i|%j|%t|%M|%L|%D|%C|%b|%R|%l|%u|%A"   # 同 slurmtop 的 SQUEUE


def uuid(i, node="n1"):
    return "GPU-%08x-%s-0000-0000-%012x" % (0x5a17 + i, node.encode().hex()[:4].ljust(4, "0"), i)


def gpu_line(i, util, mem, temp, power, total=H200_MIB, node="n1"):
    """nvidia-smi --query-gpu 的一行，欄位順序同 GPU_Q。"""
    return f"{i}, {uuid(i, node)}, {util}, {mem}, {total}, {temp}, {power}"


def proc_line(i, pid, mem, name, node="n1"):
    """--query-compute-apps 的一行，欄位順序同 PROC_Q。"""
    return f"{uuid(i, node)}, {pid}, {mem}, {name}"


DISK_42 = "1843200000 774144000 1069056000"      # df -Pk / 的 KiB：1.7T 用了 42%


def remote(gpus=(), procs=(), jobs=(), cpu="cpu  1000 0 500 8000 100 0 20 0 0 0",
           load="7.0 6.5 6.1", ncpu=224, mem=(2063000, 976000), disk=DISK_42,
           net="918273645 123456789", extra=None):
    """組出一份 REMOTE 的輸出。參數順序跟腳本的段落一樣。jobs 是 "pid job user"。"""
    out = ["@@cpu", cpu, "@@load", load, str(ncpu), "@@mem", "%d %d" % mem, "@@gpu"]
    out += list(gpus)
    out += ["@@proc"] + list(procs)
    out += ["@@jobs"] + list(jobs)
    for name, body in (extra or {}).items():       # 其他廠牌的 GPU 段落（applegpu、amdgpu…）
        out += ["@@" + name, body]
    out += ["@@disk", disk, "@@net", net]
    return "\n".join(out) + "\n"


# 這台 M3 MacBook 上 ioreg -r -d 1 -w 0 -c IOAccelerator 的真實輸出（grep 過）
IOREG_M3 = """\
+-o AGXAcceleratorG15G  <class AGXAcceleratorG15G, id 0x100000481, registered, matched, active, busy 0 (517 ms), retain 88>
      "PerformanceStatistics" = {"In use system memory (driver)"=0,"Alloc system memory"=5437849600,"Tiler Utilization %"=26,"recoveryCount"=0,"lastRecoveryTime"=0,"Renderer Utilization %"=25,"TiledSceneBytes"=884736,"Device Utilization %"=26,"SplitSceneCount"=0,"Allocated PB Size"=97648640,"In use system memory"=862388224}
      "model" = "Apple M3"
      "gpu-core-count" = 10"""


def scontrol_job(jid, user, state, alloc, name="job"):
    """scontrol -d -o show job 的一行。alloc 是 [(節點清單, GRES 字串)]。"""
    head = (f"JobId={jid} JobName={name} UserId={user}(1001) GroupId={user}(1001) "
            f"Priority=1 JobState={state} Reason=None NumNodes={len(alloc) or 1} "
            f"TresPerNode=gres/gpu:8")
    detail = "".join(f" Nodes={n} CPU_IDs=0-31 Mem=0 GRES={g}" for n, g in alloc)
    return head + detail


def idle_gpus(base_temp=30, node="n1"):
    return [gpu_line(i, 0, 1, base_temp + i % 3, "%.2f" % (75 + i), node=node) for i in range(8)]


def full_gpus(base_temp=62, node="n1"):
    return [gpu_line(i, 100 if i % 3 else 98, 122640, base_temp + i % 3 * 3,
                     "%.2f" % (648 + i * 4), node=node) for i in range(8)]


def sinfo(states):
    return "".join(f"{n}|{st}|{c}|742000/2063000\n" for n, st, c in states)


def squeue_line(jid, name, st, used, left, nnodes, cpus, gres, where, limit, user, raw=None):
    return "|".join(map(str, [jid, name, st, used, left, nnodes, cpus, gres, where, limit,
                              user, raw or jid]))


def write(scn, files):
    d = os.path.join(HERE, scn)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, "node"))
    for name, body in files.items():
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            f.write(body)


def slurm_common(nodes=("n1", "n2")):
    return {
        "hostname.txt": "n1\n",
        "sinfo_nodes.txt": "".join(n + "\n" for n in nodes),
        "scontrol_nodes.txt": "".join(f"NodeName={n} Arch=x86_64 NodeHostName={n} State=IDLE\n"
                                      for n in nodes),
        "scontrol_config.txt": "ClusterName = hipac-team3\nSlurmctldHost = n1\n",
    }


def main():
    # 1. 兩台 x 8 張，全部閒置、佇列是空的
    write("idle2x8", {**slurm_common(),
                      "sinfo.txt": sinfo([("n1", "idle", "0/224/0/224"),
                                          ("n2", "idle", "0/224/0/224")]),
                      "squeue.txt": "",
                      "node/n1.txt": remote(idle_gpus(), load="0.3 0.2 0.1"),
                      "node/n2.txt": remote(idle_gpus(31, "n2"), load="0.1 0.1 0.1")})

    # 2. 兩台 x 8 張，全部滿載，佇列有跑的也有排隊的
    full_q = [
        squeue_line(871, "hawks-mxp16", "R", "12:32", "47:28", 1, 224, "gres/gpu:8", "n1", "1:00:00", "hawks"),
        squeue_line(872, "hawks-qe-pw", "R", "9:24", "20:36", 1, 224, "gres/gpu:8", "n2", "30:00", "hawks"),
        squeue_line(873, "hawks-eagle", "PD", "0:00", "2:00:00", 1, 32, "gres/gpu:4", "(Resources)", "2:00:00", "lin"),
        squeue_line(874, "hawks-cfd", "PD", "0:00", "3:00:00", 1, 14, "N/A", "(Dependency)", "3:00:00", "chen"),
    ]
    full_procs1 = [proc_line(i, 41000 + i, 122000, "/usr/bin/python3") for i in range(8)]
    full_procs2 = [proc_line(i, 52000 + i, 122000, "/opt/qe/bin/pw.x", "n2") for i in range(8)]
    write("full2x8", {**slurm_common(),
                      "sinfo.txt": sinfo([("n1", "allocated", "224/0/0/224"),
                                          ("n2", "allocated", "224/0/0/224")]),
                      "squeue.txt": "\n".join(full_q) + "\n",
                      "scontrol_jobs.txt": "\n".join([
                          scontrol_job(871, "hawks", "RUNNING", [("n1", "gpu:h200:8(IDX:0-7)")]),
                          scontrol_job(872, "hawks", "RUNNING", [("n2", "gpu:h200:8(IDX:0-7)")]),
                          scontrol_job(873, "lin", "PENDING", []),
                          scontrol_job(874, "chen", "PENDING", [])]) + "\n",
                      "node/n1.txt": remote(full_gpus(), full_procs1,
                                            [f"{41000 + i} 871 hawks" for i in range(8)],
                                            load="18.2 8.1 7.3"),
                      "node/n2.txt": remote(full_gpus(56, "n2"), full_procs2,
                                            [f"{52000 + i} 872 hawks" for i in range(8)],
                                            load="17.9 8.0 7.0")})

    # 3. GPU 欄位含 [N/A]：n1 開了 MIG（使用率讀不到）、有張卡功耗讀不到、還有空欄位
    na_gpus = [
        gpu_line(0, "[N/A]", 20480, 41, "[N/A]"),
        gpu_line(1, "[N/A]", 0, 39, "118.20"),
        gpu_line(2, 55, 40960, "[N/A]", "[N/A]"),
        gpu_line(3, "", "", "", ""),
        gpu_line(4, "[Not Supported]", 1, 33, "[Unknown Error]"),
        gpu_line(5, 12, 4096, 35, "142.00"),
        gpu_line(6, 0, 1, 31, "76.00"),
        gpu_line(7, 0, 1, 31, "76.00"),
    ]
    na_procs = [proc_line(0, 61000, "[N/A]", "/usr/bin/python3"),
                proc_line(2, 61001, 40000, "/usr/bin/python3")]
    write("na_fields", {**slurm_common(),
                        "sinfo.txt": sinfo([("n1", "mixed", "32/192/0/224"),
                                            ("n2", "idle", "0/224/0/224")]),
                        "squeue.txt": squeue_line(900, "mig-test", "R", "5:00", "55:00", 1, 32,
                                                  "gres/gpu:2", "n1", "1:00:00", "lin") + "\n",
                        "node/n1.txt": remote(na_gpus, na_procs, ["61000 900 lin", "61001 900 lin"]),
                        "node/n2.txt": remote(idle_gpus(node="n2"))})

    # 4. 一台節點卡住不回應（n2 睡 30 秒）
    write("hang", {**slurm_common(),
                   "sinfo.txt": sinfo([("n1", "idle", "0/224/0/224"),
                                       ("n2", "idle", "0/224/0/224")]),
                   "squeue.txt": "",
                   "node/n1.txt": remote(idle_gpus()),
                   "node/n2.hang": "30\n"})

    # 5. 一台節點連不上（ssh 失敗，什麼都沒回）
    write("unreachable", {**slurm_common(),
                          "sinfo.txt": sinfo([("n1", "idle", "0/224/0/224"),
                                              ("n2", "down*", "0/0/224/224")]),
                          "squeue.txt": "",
                          "node/n1.txt": remote(idle_gpus())})

    # 6. 沒有 GPU 的機器：一台 macOS 筆電（CPU% 直接給百分比）、一台 Linux 伺服器，沒有 Slurm
    write("nogpu", {"hostname.txt": "mac\n",
                    "node/mac.txt": remote(cpu="PCT 23.4", load="2.10 2.31 2.50", ncpu=8,
                                           mem=(16384, 11800),
                                           disk="971350180 487314376 448005680"),
                    "node/cpu1.txt": remote(load="3.0 2.0 1.0", ncpu=64, mem=(257000, 64000))})

    # 7. squeue 的 %b 三種寫法同時出現（舊版 gres:gpu:N、新版 gres/gpu:N、帶型號）
    gres_q = [
        squeue_line(1001, "old-style", "R", "1:00:00", "1:00:00", 1, 32, "gres:gpu:8", "n1", "2:00:00", "hawks"),
        squeue_line(1002, "new-style", "R", "30:00", "30:00", 1, 32, "gres/gpu:8", "n2", "1:00:00", "lin"),
        squeue_line(1003, "typed", "PD", "0:00", "4:00:00", 1, 32, "gres/gpu:h200:8", "(Resources)", "4:00:00", "chen"),
        squeue_line(1004, "old-typed", "PD", "0:00", "1:00:00", 1, 16, "gres:gpu:h200:2", "(Priority)", "1:00:00", "chen"),
        squeue_line(1005, "cpu-only", "PD", "0:00", "1:00:00", 1, 4, "N/A", "(Priority)", "1:00:00", "wu"),
        squeue_line("1006_3", "array", "PD", "0:00", "1:00:00", 1, 4, "gres/gpu:1", "(Priority)", "1:00:00", "wu", 1009),
    ]
    write("gres", {**slurm_common(),
                   "sinfo.txt": sinfo([("n1", "allocated", "224/0/0/224"),
                                       ("n2", "mixed", "32/192/0/224")]),
                   "squeue.txt": "\n".join(gres_q) + "\n",
                   "node/n1.txt": remote(full_gpus()),
                   "node/n2.txt": remote(idle_gpus(node="n2"))})

    # 8. 很長的佇列：60 個 job
    long_q = []
    for k in range(60):
        run = k < 6
        long_q.append(squeue_line(2000 + k, f"sweep-{k:02d}", "R" if run else "PD",
                                  "1:%02d:00" % k if run else "0:00", "22:00:00" if run else "1-00:00:00",
                                  1, 16, "gres/gpu:1", "n%d" % (k % 2 + 1) if run else "(Priority)",
                                  "1-00:00:00", ["hawks", "lin", "chen", "wu"][k % 4]))
    write("longq", {**slurm_common(),
                    "sinfo.txt": sinfo([("n1", "mixed", "48/176/0/224"),
                                        ("n2", "mixed", "48/176/0/224")]),
                    "squeue.txt": "\n".join(long_q) + "\n",
                    "node/n1.txt": remote(idle_gpus()),
                    "node/n2.txt": remote(idle_gpus(node="n2"))})

    # 10. 佔著卻閒置：
    #   n1 的 881（lin）分到 G0-3，只有 G0、G1 有行程在跑，G2、G3 沒有行程也沒在用
    #   n1 的 882（chen）分到 G4-7，四張都有行程但使用率 0（卡住的 job）
    #   n2 的 883（hawks）分到 G0-3 在跑；G4-6 沒人用；G7 上有個 root 的非 Slurm 行程
    #   另外 884 是陣列 job 1006_3（%A 是 1009），在 n2 G4 上，cgroup 寫的是 job_1009
    held_q = [
        squeue_line(881, "train-lm", "R", "3:10:00", "20:50:00", 1, 64, "gres/gpu:h200:4", "n1", "1-00:00:00", "lin"),
        squeue_line(882, "stuck-eval", "R", "5:00:00", "19:00:00", 1, 64, "gres/gpu:4", "n1", "1-00:00:00", "chen"),
        squeue_line(883, "hawks-mxp", "R", "40:00", "20:00", 1, 64, "gres/gpu:4", "n2", "1:00:00", "hawks"),
        squeue_line("1006_3", "sweep", "R", "1:00", "59:00", 1, 4, "gres/gpu:1", "n2", "1:00:00", "wu", 1009),
        squeue_line(885, "waiting", "PD", "0:00", "2:00:00", 1, 32, "gres/gpu:8", "(Resources)", "2:00:00", "lin"),
    ]
    n1 = [gpu_line(0, 91, 60000, 55, "520.00"), gpu_line(1, 88, 60000, 54, "515.00"),
          gpu_line(2, 0, 1, 33, "76.00"), gpu_line(3, 0, 1, 33, "76.00")] + \
         [gpu_line(i, 0, 30000, 36, "110.00") for i in range(4, 8)]
    n1p = [proc_line(0, 7100, 60000, "python"), proc_line(1, 7101, 60000, "python")] + \
          [proc_line(i, 7200 + i, 30000, "eval.py") for i in range(4, 8)]
    n1j = ["7100 881 lin", "7101 881 lin"] + [f"{7200 + i} 882 chen" for i in range(4, 8)]
    n2 = [gpu_line(i, 97, 90000, 60, "600.00", node="n2") for i in range(4)] + \
         [gpu_line(4, 64, 5000, 44, "300.00", node="n2")] + \
         [gpu_line(i, 0, 1, 31, "75.00", node="n2") for i in range(5, 7)] + \
         [gpu_line(7, 0, 300, 32, "80.00", node="n2")]
    n2p = [proc_line(i, 8100 + i, 90000, "mxp", "n2") for i in range(4)] + \
          [proc_line(4, 8300, 5000, "sweep", "n2"), proc_line(7, 900, 300, "/usr/lib/xorg/Xorg", "n2")]
    n2j = [f"{8100 + i} 883 hawks" for i in range(4)] + ["8300 1009 wu", "900 - root"]
    write("idleheld", {**slurm_common(),
                       "sinfo.txt": sinfo([("n1", "mixed", "128/96/0/224"),
                                           ("n2", "mixed", "68/156/0/224")]),
                       "squeue.txt": "\n".join(held_q) + "\n",
                       "scontrol_jobs.txt": "\n".join([
                           scontrol_job(881, "lin", "RUNNING", [("n1", "gpu:h200:4(IDX:0-3)")]),
                           scontrol_job(882, "chen", "RUNNING", [("n1", "gpu:h200:4(IDX:4-7)")]),
                           scontrol_job(883, "hawks", "RUNNING", [("n2", "gpu:h200:4(IDX:0-3)")]),
                           scontrol_job(1009, "wu", "RUNNING", [("n2", "gpu:h200:1(IDX:4)")]),
                           scontrol_job(885, "lin", "PENDING", [])]) + "\n",
                       "node/n1.txt": remote(n1, n1p, n1j),
                       "node/n2.txt": remote(n2, n2p, n2j)})

    # 11. 警示列：n1 磁碟 95%、G3/G5 過熱；n2 的 G6 被 886 佔著沒用；n3 連不上；n4 一切正常
    hot = [gpu_line(i, 99, 120000, 70, "690.00") for i in range(8)]
    hot[3] = gpu_line(3, 99, 120000, 84, "700.00")
    hot[5] = gpu_line(5, 99, 120000, 80, "700.00")
    n2a = [gpu_line(i, 0, 1, 30, "75.00", node="n2") for i in range(8)]
    write("alerts", {**slurm_common(("n1", "n2", "n3", "n4")),
                     "sinfo.txt": sinfo([("n1", "mixed", "32/192/0/224"), ("n2", "mixed", "8/216/0/224"),
                                         ("n3", "down*", "0/0/224/224"), ("n4", "idle", "0/224/0/224")]),
                     "squeue.txt": squeue_line(886, "notebook", "R", "2:00:00", "6:00:00", 1, 8,
                                               "gres/gpu:1", "n2", "8:00:00", "wu") + "\n",
                     "scontrol_jobs.txt": scontrol_job(886, "wu", "RUNNING",
                                                       [("n2", "gpu:h200:1(IDX:6)")]) + "\n",
                     "node/n1.txt": remote(hot, disk="1843200000 1733000000 91000000"),
                     "node/n2.txt": remote(n2a),
                     "node/n4.txt": remote(idle_gpus(node="n4"))})

    # 12. 16 台節點：面板放不下，自動改成密集檢視。gpu07 連不上。
    names = ["gpu%02d" % i for i in range(1, 17)]
    many = {**slurm_common(names), "hostname.txt": "gpu01\n",
            "sinfo.txt": sinfo([(n, "mixed", "112/112/0/224") for n in names]),
            "squeue.txt": squeue_line(990, "big-sweep", "R", "1:00:00", "3:00:00", 8, 1792,
                                      "gres/gpu:8", "gpu[01-08]", "4:00:00", "hawks") + "\n"}
    for k, n in enumerate(names):
        if n == "gpu07":
            continue
        many["node/%s.txt" % n] = remote(full_gpus(node=n) if k % 3 == 0 else idle_gpus(node=n),
                                         load="%d.0 5.0 4.0" % k)
    write("many", many)

    # 13. Apple Silicon 筆電（這台 M3 錄下來的）：沒有 nvidia-smi、沒有 Slurm
    write("applesilicon", {"hostname.txt": "m3\n",
                           "node/m3.txt": remote(cpu="PCT 41.1", load="4.12 4.27 3.77", ncpu=8,
                                                 mem=(16384, 12144),
                                                 disk="971350180 487314376 448005680",
                                                 extra={"applegpu": IOREG_M3})})

    # 14. AMD 節點（8 張 MI300X，amdgpu sysfs）：沒有 nvidia-smi。
    #     job 950 分到 IDX 0-3 在跑；951 分到 IDX 4-5 卻沒在用
    mi = []
    for i in range(8):
        busy = 93 if i < 4 else 0
        mi.append("card%d %d %d %d %d %d %016x" % (i + 1, busy, (150 if i < 4 else 2) * 1024 ** 3,
                                                   192 * 1024 ** 3, (68 if i < 4 else 38) * 1000,
                                                   (650 if i < 4 else 140) * 10 ** 6, 0xabc0 + i))
    write("amd", {**slurm_common(("m1",)), "hostname.txt": "m1\n",
                  "sinfo.txt": sinfo([("m1", "mixed", "96/96/0/192")]),
                  "squeue.txt": "\n".join([
                      squeue_line(950, "rocm-train", "R", "2:00:00", "10:00:00", 1, 64,
                                  "gres/gpu:mi300x:4", "m1", "12:00:00", "hawks"),
                      squeue_line(951, "idle-nb", "R", "1:00:00", "3:00:00", 1, 32,
                                  "gres/gpu:mi300x:2", "m1", "4:00:00", "chen")]) + "\n",
                  "scontrol_jobs.txt": "\n".join([
                      scontrol_job(950, "hawks", "RUNNING", [("m1", "gpu:mi300x:4(IDX:0-3)")]),
                      scontrol_job(951, "chen", "RUNNING", [("m1", "gpu:mi300x:2(IDX:4-5)")])]) + "\n",
                  "node/m1.txt": remote(ncpu=192, extra={"amdgpu": "\n".join(mi)})})

    # 15. Jetson AGX Orin 邊緣裝置：沒有 nvidia-smi、沒有 Slurm
    write("jetson", {"hostname.txt": "orin\n",
                     "node/orin.txt": remote(load="3.1 2.8 2.5", ncpu=12, mem=(62841, 18230),
                                             disk="61255492 40171432 18554252",
                                             extra={"jetson": "734 47500 NVIDIA_Jetson_AGX_Orin"})})

    # 16. 惡意字串：別的使用者把終端機控制序列塞進 job 名稱、使用者、行程名稱
    osc52 = "evil\x1b]52;c;cm0gLXJmIH4=\x07job"            # 寫剪貼簿
    clear = "/tmp/\x1b[2J\x1b[Hwipe"                         # 清畫面、移游標
    title = "mal\x1b]0;pwned\x07lory"                        # 改視窗標題
    write("hostile", {**slurm_common(("n1",)),
                      "sinfo.txt": sinfo([("n1", "mixed", "8/216/0/224")]),
                      "squeue.txt": squeue_line(990, osc52, "R", "1:00", "59:00", 1, 8, "gres/gpu:1",
                                                "n1", "1:00:00", title) + "\n",
                      "scontrol_jobs.txt": scontrol_job(990, title, "RUNNING",
                                                        [("n1", "gpu:h200:1(IDX:0)")]) + "\n",
                      "node/n1.txt": remote(idle_gpus(), [proc_line(0, 4242, 100, clear)],
                                            ["4242 990 " + title])})

    # 9. 連續兩次取樣（CPU% 要兩筆 /proc/stat 才算得出來）
    write("seq", {"hostname.txt": "n1\n",
                  "node/n1.1.txt": remote(cpu="cpu  1000 0 500 8000 100 0 20 0 0 0",
                                          net="1000000 2000000"),
                  "node/n1.2.txt": remote(cpu="cpu  1600 0 700 8100 100 0 20 0 0 0",
                                          net="3097152 2204800"),
                  "node/n1.txt": remote(cpu="cpu  2200 0 900 8200 100 0 20 0 0 0")})


if __name__ == "__main__":
    main()
