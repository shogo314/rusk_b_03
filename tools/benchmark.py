#!/usr/bin/env python3
"""Compare generated C++, handwritten C++, and PyPy; compilation is not timed."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
RANGE_RUSK = 'in n:Int; let total:=0; for i in 0..n { total+=i; } wt total;'
RANGE_CPP = '#include <iostream>\nint main(){long long n,total=0;std::cin>>n;for(long long i=0;i<n;++i)total+=i;std::cout<<total<<"\\n";}'
RANGE_PY = 'n=int(input()); total=0\nfor i in range(n): total+=i\nprint(total)\n'
SEARCH_CPP = '''#include <bits/stdc++.h>
int main(){std::ios::sync_with_stdio(false);std::cin.tie(nullptr);int n,q;std::cin>>n>>q;std::vector<long long>a(n);for(auto& x:a)std::cin>>x;std::stable_sort(a.begin(),a.end());while(q--){long long x;std::cin>>x;std::cout<<(std::upper_bound(a.begin(),a.end(),x)-a.begin())<<'\\n';}}'''
SEARCH_PY = '''import sys,bisect
it=iter(map(int,sys.stdin.buffer.read().split()));n=next(it);q=next(it)
a=sorted(next(it) for _ in range(n))
sys.stdout.write(''.join(str(bisect.bisect_right(a,next(it)))+'\\n' for _ in range(q)))
'''
GRID_CPP = '''#include <bits/stdc++.h>
int main(){int h,w;std::cin>>h>>w;std::vector<std::string>g(h);for(auto& r:g)std::cin>>r;std::vector<std::vector<int>>d(h,std::vector<int>(w,-1));std::queue<std::pair<int,int>>q;if(g[0][0]!='#'){d[0][0]=0;q.push({0,0});}int dr[]={1,-1,0,0},dc[]={0,0,1,-1};while(!q.empty()){auto[r,c]=q.front();q.pop();for(int i=0;i<4;i++){int nr=r+dr[i],nc=c+dc[i];if(nr>=0&&nr<h&&nc>=0&&nc<w&&g[nr][nc]!='#'&&d[nr][nc]<0){d[nr][nc]=d[r][c]+1;q.push({nr,nc});}}}std::cout<<d[h-1][w-1]<<'\\n';}'''
GRID_PY = '''import sys
from collections import deque
h,w=map(int,sys.stdin.buffer.readline().split());g=[sys.stdin.buffer.readline().strip() for _ in range(h)];d=[[-1]*w for _ in range(h)];q=deque()
if g[0][0]!=35:d[0][0]=0;q.append((0,0))
while q:
 r,c=q.popleft()
 for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
  nr,nc=r+dr,c+dc
  if 0<=nr<h and 0<=nc<w and g[nr][nc]!=35 and d[nr][nc]<0:d[nr][nc]=d[r][c]+1;q.append((nr,nc))
print(d[h-1][w-1])
'''

def version(command):
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return (result.stdout or result.stderr).strip().splitlines()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/debug/rusk')
    parser.add_argument('--baseline-compiler', type=Path, help='compare a previous Rusk compiler on the same inputs')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    pypy = shutil.which('pypy3')
    n, q, h, w = 200_000, 2_000, 200, 200
    values = [(i*7919)%1_000_003 for i in range(n)]
    queries = [(i*12347)%1_000_003 for i in range(q)]
    jobs = [
        ('range_sum', RANGE_RUSK, RANGE_CPP, RANGE_PY, b'1000000\n', 'N=1,000,000'),
        ('sort_search', (ROOT/'examples/prototype/sort_search.rusk').read_text(), SEARCH_CPP, SEARCH_PY,
         (f'{n} {q}\n'+' '.join(map(str,values))+'\n'+' '.join(map(str,queries))+'\n').encode(), 'N=200,000; Q=2,000'),
        ('grid_bfs', (ROOT/'examples/prototype/grid_bfs.rusk').read_text(), GRID_CPP, GRID_PY,
         (f'{h} {w}\n'+('.'*w+'\n')*h).encode(), '200×200 open grid'),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix='rusk-benchmark-') as directory:
        temp = Path(directory)
        for name, rusk, cpp, python, data, size in jobs:
            (temp/'main.rusk').write_text(rusk)
            subprocess.run([str(args.compiler.resolve()),'compile',str(temp/'main.rusk'),'-o',str(temp/'rusk.cpp')],check=True)
            (temp/'native.cpp').write_text(cpp)
            (temp/'baseline.py').write_text(python)
            for label in ['rusk','native']:
                subprocess.run(['g++','-std=c++20','-O2',str(temp/f'{label}.cpp'),'-o',str(temp/label)],check=True)
            commands = {'C++':[str(temp/'native')], 'Rusk':[str(temp/'rusk')]}
            if args.baseline_compiler:
                subprocess.run([str(args.baseline_compiler.resolve()),'compile',str(temp/'main.rusk'),'-o',str(temp/'previous.cpp')],check=True)
                subprocess.run(['g++','-std=c++20','-O2',str(temp/'previous.cpp'),'-o',str(temp/'previous')],check=True)
                commands['Rusk baseline']=[str(temp/'previous')]
            if pypy:
                commands['PyPy']=[pypy,str(temp/'baseline.py')]
            reference = None
            row = {'name':name, 'size':size, 'seconds':{}}
            for label, command in commands.items():
                samples=[]
                for _ in range(args.repeats):
                    start=time.perf_counter()
                    run=subprocess.run(command,input=data,capture_output=True,check=True)
                    samples.append(time.perf_counter()-start)
                    if reference is None:
                        reference=run.stdout
                    if run.stdout != reference:
                        raise RuntimeError(f'{name}: output mismatch in {label}')
                row['seconds'][label]=statistics.median(samples)
            results.append(row)
    report = {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'platform':platform.platform(),
              'cpu':next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')), 'unknown'),
              'g++':version(['g++','--version']), 'pypy':version([pypy,'--version']) if pypy else None,
              'repeats':args.repeats, 'results':results}
    output=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    print(output,end='')
    if args.output:
        args.output.write_text(output)

if __name__ == '__main__':
    main()
