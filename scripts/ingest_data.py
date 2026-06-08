"""data/ 폴더의 PDF 를 읽어 vector store 에 적재하는 일회성 스크립트.

사용:
    .venv/Scripts/python.exe scripts/ingest_data.py            # data/*.pdf 전부 적재
    .venv/Scripts/python.exe scripts/ingest_data.py "질문"      # 적재 후 샘플 검색까지

로컬 임베디드 Qdrant(.env 의 VECTOR_DB_URL=./.qdrant_local)는 단일 프로세스만
열 수 있으므로, 적재 중에는 API 서버를 띄우지 말 것.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Windows 콘솔(cp949)에서도 한글/유니코드 출력이 깨지지 않게 stdout 을 utf-8 로.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 스크립트를 직접 실행해도 app 패키지를 임포트할 수 있게 루트를 경로에 추가.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pypdf import PdfReader  # noqa: E402

from app.services.ir.vector.ingest import ingest  # noqa: E402
from app.services.ir.vector.search import VectorRetriever  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def main() -> None:
    pdfs = sorted(DATA_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"[!] data/ 에 PDF 가 없습니다: {DATA_DIR}")
        return

    print(f"[*] {len(pdfs)}개 PDF 적재 시작 (최초 1회 bge-m3 모델 다운로드가 있습니다)...")
    total = 0
    for pdf in pdfs:
        text = extract_pdf_text(pdf)
        if not text.strip():
            print(f"  - {pdf.name}: 텍스트 추출 0 (스캔본일 수 있음) → 건너뜀")
            continue
        n = await ingest(pdf.stem, text, {"filename": pdf.name})
        print(f"  - {pdf.name}: {n} chunks")
        total += n
    print(f"[*] 완료: {len(pdfs)}개 파일, 총 {total} chunks")

    # 인자로 질문을 주면 적재 직후 샘플 검색을 보여준다(같은 프로세스라 로컬모드 OK).
    query = sys.argv[1] if len(sys.argv) > 1 else "모형 검증 방법론"
    print(f"\n[*] 샘플 검색: {query!r}")
    chunks = await VectorRetriever().retrieve(query, top_k=3)
    if not chunks:
        print("  (검색 결과 없음)")
    for c in chunks:
        print(f"  [{c.score:.3f}] {c.source_id}: {c.content[:80].strip()}...")


if __name__ == "__main__":
    asyncio.run(main())
