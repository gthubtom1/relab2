# -*- coding: utf-8 -*-
"""并发对照：同一批题、同一批模型，先高并发后低并发，比较 传输错误率 与 耗时。
结论用来定 sweep 的默认并发。"""
import sys,time,threading,json,io
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0,'.')
import sweep as S
S._load_models()
ITEMS=["E1","E2","E3","E8","E31","E40"]
Q={i:t for i,t in S.ITEMS}
MODELS=[("mimo-v2.6-flash-free","base/mimo-2.6.md"),("space-bunny-free","base/space-bunny.md")]
CARDS={m:S.load_card(c)[0] for m,c in MODELS}

def leg(workers,per,name):
    S.SEM={m:threading.Semaphore(per) for m,_ in MODELS}
    jobs=[(m,i) for m,_ in MODELS for i in ITEMS]
    res=[]
    def one(j):
        m,i=j; t0=time.time()
        t,rea,us,st=S.raw(m,CARDS[m],Q[i])
        return (m,i,st,len(t),round(time.time()-t0,1))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in as_completed([ex.submit(one,j) for j in jobs]): res.append(r)
    ok=sum(1 for r in res if r[3]>0); err=[r for r in res if r[3]==0]
    lat=sorted(r[4] for r in res)
    print("[%s] workers=%d per_model=%d | 有正文 %d/%d | 传输失败 %d | 中位耗时 %.1fs | 最慢 %.1fs"%(
        name,workers,per,ok,len(res),len(err),lat[len(lat)//2],lat[-1]))
    for r in err: print("     失败 %-34s %-22s %s"%(r[0],r[2],r[1]))
    return len(err)

e1=leg(12,6,"高并发")
e2=leg(1,1,"低并发")
print("\n结论：高并发 %d 个传输失败 -> 低并发 %d 个。"%(e1,e2))
