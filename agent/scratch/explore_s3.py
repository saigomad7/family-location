"""S3에 뭐가 있는지 눈으로 보는 셀 스크립트.

Spyder에서 셀(#%%) 단위로 Ctrl+Enter. df 를 변수 탐색기에서 더블클릭하면
버킷 내용이 표로 열린다.
"""

# %% 준비
from myagent import storage
from myagent.config import get_settings

s = get_settings()
print(s.s3_endpoint, s.s3_bucket)

# %% 최상위에 뭐가 있나 (변수 탐색기에서 df 확인)
df = storage.ls("", limit=200)
df.head(30)

# %% 특정 prefix 만
df_raw = storage.ls("raw/", limit=500)
df_raw.groupby(df_raw["key"].str.split("/").str[1]).size()

# %% 파일 하나 로컬로 가져와서 열어보기
key = df["key"].iloc[0]
path = storage.fetch(key)     # 두 번째부터는 캐시에서 즉시
print(path)
print(path.read_text(encoding="utf-8", errors="replace")[:800])

# %% 로컬 캐시에 뭐가 쌓였나 (디스크 정리용)
cache = storage.cache_report()
cache.head(20)
