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
SQUEUE_FMT = "%i|%j|%t|%M|%L|%D|%C|%b|%R|%l|%u"      # 同 slurmtop 的 SQUEUE


def gpu_line(i, util, mem, temp, power, total=H200_MIB):
    """nvidia-smi --query-gpu 的一行，欄位順序同 GPU_Q。"""
    return f"{i}, {util}, {mem}, {total}, {temp}, {power}"


def remote(gpus=(), procs=(), cpu="cpu  1000 0 500 8000 100 0 20 0 0 0",
           load="7.0 6.5 6.1", ncpu=224, mem=(2063000, 976000)):
    """組出一份 REMOTE 的輸出。參數順序跟腳本的段落一樣。"""
    out = ["@@cpu", cpu, "@@load", load, str(ncpu), "@@mem", "%d %d" % mem, "@@gpu"]
    out += list(gpus)
    out += ["@@proc"] + list(procs)
    return "\n".join(out) + "\n"


def idle_gpus(base_temp=30):
    return [gpu_line(i, 0, 1, base_temp + i % 3, "%.2f" % (75 + i)) for i in range(8)]


def full_gpus(base_temp=62):
    return [gpu_line(i, 100 if i % 3 else 98, 122640, base_temp + i % 3 * 3,
                     "%.2f" % (648 + i * 4)) for i in range(8)]


def sinfo(states):
    return "".join(f"{n}|{st}|{c}|742000/2063000\n" for n, st, c in states)


def squeue_line(jid, name, st, used, left, nnodes, cpus, gres, where, limit, user, raw=None):
    return "|".join(map(str, [jid, name, st, used, left, nnodes, cpus, gres, where, limit,
                              user]))


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
                      "node/n2.txt": remote(idle_gpus(31), load="0.1 0.1 0.1")})

    # 2. 兩台 x 8 張，全部滿載，佇列有跑的也有排隊的
    full_q = [
        squeue_line(871, "hawks-mxp16", "R", "12:32", "47:28", 2, 448, "gres/gpu:8", "n[1-2]", "1:00:00", "hawks"),
        squeue_line(872, "hawks-qe-pw", "R", "9:24", "20:36", 1, 224, "gres/gpu:8", "n2", "30:00", "hawks"),
        squeue_line(873, "hawks-eagle", "PD", "0:00", "2:00:00", 1, 32, "gres/gpu:4", "(Resources)", "2:00:00", "lin"),
        squeue_line(874, "hawks-cfd", "PD", "0:00", "3:00:00", 1, 14, "N/A", "(Dependency)", "3:00:00", "chen"),
    ]
    full_procs1 = [f"{41000 + i}, 122000, /usr/bin/python3" for i in range(8)]
    full_procs2 = [f"{52000 + i}, 122000, /opt/qe/bin/pw.x" for i in range(8)]
    write("full2x8", {**slurm_common(),
                      "sinfo.txt": sinfo([("n1", "allocated", "224/0/0/224"),
                                          ("n2", "allocated", "224/0/0/224")]),
                      "squeue.txt": "\n".join(full_q) + "\n",
                      "node/n1.txt": remote(full_gpus(), full_procs1, load="18.2 8.1 7.3"),
                      "node/n2.txt": remote(full_gpus(56), full_procs2, load="17.9 8.0 7.0")})

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
    na_procs = ["61000, [N/A], /usr/bin/python3",
                "61001, 40000, /usr/bin/python3"]
    write("na_fields", {**slurm_common(),
                        "sinfo.txt": sinfo([("n1", "mixed", "32/192/0/224"),
                                            ("n2", "idle", "0/224/0/224")]),
                        "squeue.txt": squeue_line(900, "mig-test", "R", "5:00", "55:00", 1, 32,
                                                  "gres/gpu:2", "n1", "1:00:00", "lin") + "\n",
                        "node/n1.txt": remote(na_gpus, na_procs),
                        "node/n2.txt": remote(idle_gpus())})

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
                                           mem=(16384, 11800)),
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
                   "node/n2.txt": remote(idle_gpus())})

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
                    "node/n2.txt": remote(idle_gpus())})

    # 9. 連續兩次取樣（CPU% 要兩筆 /proc/stat 才算得出來）
    write("seq", {"hostname.txt": "n1\n",
                  "node/n1.1.txt": remote(cpu="cpu  1000 0 500 8000 100 0 20 0 0 0"),
                  "node/n1.2.txt": remote(cpu="cpu  1600 0 700 8100 100 0 20 0 0 0"),
                  "node/n1.txt": remote(cpu="cpu  2200 0 900 8200 100 0 20 0 0 0")})


if __name__ == "__main__":
    main()
