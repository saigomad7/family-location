"""Spyder 세션을 열 때 콘솔에서 제일 먼저 실행하는 파일.

Spyder에서:  runfile('scratch/bootstrap.py')
또는 이 파일을 열고 F5.

autoreload 덕분에 src/myagent/*.py 를 고치고 저장하면 콘솔을 재시작하지 않아도
다음 셀에서 바로 반영된다. 이게 "한 줄씩 확인하며 개발"의 절반이다.
"""

from IPython import get_ipython

ipy = get_ipython()
if ipy is not None:
    ipy.run_line_magic("load_ext", "autoreload")
    ipy.run_line_magic("autoreload", "2")

from myagent.config import get_settings, reload_settings  # noqa: E402
from myagent.logging_setup import setup  # noqa: E402

s = get_settings()
setup(s.log_level)

print(f"ENV={s.env}")
print(f"S3   : {s.s3_endpoint} / {s.s3_bucket}")
print(f"MILVUS: {s.milvus_uri} / {s.milvus_collection} (dim={s.embed_dim})")
print(f"LLM  : {s.llm_model} (effort={s.llm_effort})")
print(f"CACHE: {s.cache_path.resolve()}")
print("\n.env.local 을 고쳤다면 reload_settings() 를 호출하세요.")
