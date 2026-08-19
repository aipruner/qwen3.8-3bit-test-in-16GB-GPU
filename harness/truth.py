from itertools import permutations, product
from math import isqrt, gcd
from fractions import Fraction

def zeros(n):
    c=0; p=5
    while p<=n: c+=n//p; p*=5
    return c
# 1
q1=next(n for n in range(1,10**5) if zeros(n)==100)
# 2 Pell x^2-61y^2=1
y=1
while True:
    v=61*y*y+1; x=isqrt(v)
    if x*x==v: q2=x; break
    y+=1
# 3
sq={i*i for i in range(1,10)}
q3=sum(1 for p in permutations(range(1,10)) if all(p[i]+p[i+1] in sq for i in range(8)))
# 4  六顆骰子和為 20 的機率最簡分數 a/b -> a+b
cnt=sum(1 for c in product(range(1,7),repeat=6) if sum(c)==20)
f=Fraction(cnt,6**6); q4=f.numerator+f.denominator
# 5
def isp(n):
    if n<2: return False
    for i in range(2,isqrt(n)+1):
        if n%i==0: return False
    return True
q5=sum(1 for n in range(1,201) if isp(n*n+n+41))
# 6
q6=sum(int(d) for d in str(3**1000))
# 7 最小 k>0 使 2^k 十進位以 2026 開頭
k=1
while True:
    if str(2**k).startswith("2026"): q7=k; break
    k+=1
# 8 1..10^5 中 n 與 n^2 皆為回文的個數
q8=sum(1 for n in range(1,10**5) if str(n)==str(n)[::-1] and str(n*n)==str(n*n)[::-1])
for i,v in enumerate([q1,q2,q3,q4,q5,q6,q7,q8],1): print(f"Q{i} = {v}")
