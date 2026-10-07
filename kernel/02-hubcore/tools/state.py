#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hub-lean CLI 入口。逻辑在 hub_io / hub_flow / hub_wording / hub_ask / hub_cmds；hub_gates 是门面。"""
import argparse
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
from hub_io import CANDIDATE_ROLES, PRODUCT_TYPES, RECORD_KINDS, die
from hub_work import cmd_work
from hub_cmds import (
    cmd_attempt, cmd_baseline, cmd_candidate, cmd_confirm, cmd_gate, cmd_init, cmd_plan,
    cmd_probe, cmd_accept_closed, cmd_accept_seen,
    cmd_rebind, cmd_record, cmd_recover, cmd_reopen, cmd_require, cmd_restore, cmd_status,
    cmd_verify,
)
def build_parser():
    ap = argparse.ArgumentParser(prog="state.py", description="hub-lean 项目状态的唯一写入者")
    sub = ap.add_subparsers(dest="cmd", required=True)
    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--product", required=True)
        p.set_defaults(func=fn)
        return p
    p = add("init", cmd_init, "建合同、锁 baseline")
    p.add_argument("--type", required=True, choices=PRODUCT_TYPES)
    p.add_argument("--product-id")
    p.add_argument("--upstream-version")
    p.add_argument("--primary-flow", dest="primary_flow")
    p.add_argument("--success")
    p.add_argument("--route")
    p.add_argument("--baseline", nargs="*")
    p.add_argument("--force", action="store_true")
    p.add_argument("--adopt-ledger", dest="adopt_ledger", action="store_true")
    p = add("plan", cmd_plan, "锁定 mission")
    p.add_argument("--goal", required=True)
    p.add_argument("--success", required=True)
    p.add_argument("--route", required=True)
    p.add_argument("--reason", help="已锁定 mission 发生变化时必填")
    p.add_argument("--reopen-from", dest="reopen_from")
    add("status", cmd_status, "我在哪 / 唯一下一步")
    p = add("gate", cmd_gate, "检查准备打包或最终交付的责任与证据")
    p.add_argument("--scope", choices=("package", "delivery"), default="package")
    p = add("work", cmd_work, "累积责任、派生完成、返回直接调用方")
    actions = p.add_mutually_exclusive_group()
    actions.add_argument("--define")
    actions.add_argument("--withdraw")
    actions.add_argument("--attest")
    actions.add_argument("--enter")
    actions.add_argument("--leave", action="store_true")
    p.add_argument("--pause", action="store_true")
    p.add_argument("--kind", choices=("review", "acceptance"))
    p.add_argument("--source")
    p.add_argument("--artifact")
    p.add_argument("--actor")
    p.add_argument("--phase")
    p.add_argument("--check", action="store_true")
    p.add_argument("--json", action="store_true")
    p = add("probe", cmd_probe, "运行当前阶段的机器物理探针并登记收据")
    p.add_argument("--phase", required=True)
    p.add_argument("--check", required=True)
    p.add_argument("--red", action="store_true", help="记录实现前应失败的 RED 探针结果")
    p.add_argument("--mode", choices=("change", "baseline", "regression"), default="change",
                   help="修复需 RED；基线不伪造 RED；回归需同检查的历史通过依据")
    p = add("accept-closed", cmd_accept_closed, "登记主人看见核心关上了（机器没看成或误判时）")
    p.add_argument("--phase", required=True)
    p.add_argument("--quote", required=True, help="主人原话：看见关上了什么，不是「符合要求」")
    p = add("accept-seen", cmd_accept_seen, "登记主人亲手看见的这一项（机器没看成、误判或控不了电脑时）")
    p.add_argument("--phase", required=True)
    p.add_argument("--check", required=True, help="当前阶段的检查 id，一次只登记一项")
    p.add_argument("--quote", required=True, help="主人原话：看见了什么，不是「符合要求」")
    p = add("confirm", cmd_confirm, "记一次用户确认，拒绝乱序")
    p.add_argument("--stop-point", dest="stop_point", required=True, nargs="+")
    p.add_argument("--evidence", required=True)
    p.add_argument("--note")
    p.add_argument("--ack-drift", dest="ack_drift")
    p.add_argument("--reconfirm", action="store_true")
    p = add("attempt", cmd_attempt, "记一次尝试，数同一假设重复")
    p.add_argument("--phase", required=True)
    p.add_argument("--hypothesis", required=True)
    p.add_argument("--result", required=True)
    p.add_argument("--evidence")
    p.add_argument("--hypothesis-key", dest="hypothesis_key")
    p.add_argument("--new-evidence", dest="new_evidence", action="store_true")
    p.add_argument("--blocked", action="store_true")
    p.add_argument("--routes")
    p = add("reopen", cmd_reopen, "从某阶段重开，作废其后确认")
    p.add_argument("--from", dest="from_phase", required=True)
    p.add_argument("--reason", required=True)
    p = add("record", cmd_record, "写入 manifest 制品")
    p.add_argument("--kind", required=True, choices=RECORD_KINDS)
    p.add_argument("--phase")
    p.add_argument("--data")
    p.add_argument("--data-file", dest="data_file")
    p = add("require", cmd_require, "追加或列出需求账本")
    p.add_argument("--append")
    p.add_argument("--list", dest="list_rows", action="store_true")
    p.add_argument("--id", dest="req_id")
    p.add_argument("--kind", choices=("requirement", "decision", "question"), default="requirement")
    p.add_argument("--source", help="实际用户消息的来源身份，不能把助手建议冒充决定")
    add("verify", cmd_verify, "复算 baseline 哈希")
    p = add("baseline", cmd_baseline, "锁定或更新上游 baseline")
    p.add_argument("--set", dest="set_path", nargs="*")
    p.add_argument("--upstream-version", dest="upstream_version")
    p.add_argument("--note")
    p = add("candidate", cmd_candidate, "登记当前候选文件")
    p.add_argument("--set", dest="set_path")
    p.add_argument("--set-files", dest="set_files", nargs="+")
    p.add_argument("--role", choices=CANDIDATE_ROLES)
    p.add_argument("--parent-sha", dest="parent_sha")
    p.add_argument("--note")
    p.add_argument("--revert")
    p.add_argument("--bless", action="store_true")
    p.add_argument("--show", action="store_true")
    p = add("rebind", cmd_rebind, "把合同路径改回当前产品根")
    p.add_argument("--force-identity", dest="force_identity", action="store_true")
    p = add("restore", cmd_restore, "恢复 last-good（覆盖须 --yes；删额外文件还须 --delete-extras）")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--delete-extras", dest="delete_extras", action="store_true")
    add("recover", cmd_recover, "写出恢复卡；status 会读")
    return ap
def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except SystemExit:
        raise
    except FileNotFoundError as e:
        die(f"找不到这个文件或目录：{e}\n  不是杀软锁了。检查路径写对没有。", 2)
    except PermissionError as e:
        die(f"没有权限读或写：{e}\n  不是杀软锁了。检查路径是不是目录、有没有权限。", 2)
    except OSError as e:
        die(f"文件系统忙/被占用，本次操作未完成（可能杀软或索引器临时锁了 .hub 下的文件）：{e}\n"
            f"  没有写坏任何东西，稍等一两秒重试即可。", 2)
if __name__ == "__main__":
    main()
