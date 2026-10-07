"""Merge-DAG order checker: refuses an illegal card sequence with a real non-zero exit.

Usage: check-merge-order.py --dag DAG --order "T12+T14,T21,U9,T18"
Exit codes: 0 order respects every edge | 21 illegal order | 2 usage error.
Only stdlib. No network.
"""
import json
import sys

def main():
    dag_path, order_raw = None, None
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--dag" and i + 1 < len(argv):
            dag_path = argv[i + 1]; i += 2
        elif argv[i] == "--order" and i + 1 < len(argv):
            order_raw = argv[i + 1]; i += 2
        else:
            print("usage: check-merge-order.py --dag DAG --order A,B,C", file=sys.stderr)
            return 2
    if not dag_path or order_raw is None:
        print("usage: check-merge-order.py --dag DAG --order A,B,C", file=sys.stderr)
        return 2
    dag = json.load(open(dag_path, encoding="utf-8"))
    known = {node["id"] for node in dag.get("nodes", [])}
    order = [item.strip() for item in order_raw.split(",") if item.strip()]
    position = {node: index for index, node in enumerate(order)}
    problems = []
    for node in order:
        if node not in known:
            problems.append("unknown node '%s' is fail-closed" % node)
    for edge in dag.get("edges", []):
        before, after = edge["from"], edge["to"]
        if before in position and after in position and position[before] > position[after]:
            problems.append("'%s' merged before its dependency '%s' (%s)" % (after, before, edge.get("note", "")))
    if problems:
        print("MERGE ORDER REJECTED (%d):" % len(problems))
        for item in problems:
            print("  - " + item)
        return 21
    print("merge order ok: %d node(s), %d edge(s) respected" % (len(order), len(dag.get("edges", []))))
    return 0

if __name__ == "__main__":
    sys.exit(main())
