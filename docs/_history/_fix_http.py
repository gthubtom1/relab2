import io
NL='\r\n'
P='skillpack/skills/scripts/capability-index.py'
lines=io.open(P,encoding='utf-8-sig',newline='').read().split(NL)
OLD='    (r"api (client|debugger|testing tool)", "http-client"),'
NEW=('    (r"api (client|debugger|testing tool)", "http-client"),'+NL+
     '    (r"(http|api).{0,12}(client|debugging tool).{0,20}(endpoint|request|url)", "http-client"),')
idx=[k for k,l in enumerate(lines) if l==OLD]
assert len(idx)==1, idx
lines[idx[0]:idx[0]+1]=NEW.split(NL)
io.open(P,'w',encoding='utf-8',newline='').write(NL.join(lines))
print("http rule widened")
