import asyncio
import logging
from typing import List, Optional, Tuple
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self):
        # 若有需要代理，可在外部用 HTTP(S)_PROXY 環境變數處理
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.max_retries = int(os.getenv("TRANS_MAX_RETRIES", "3"))
        self.max_concurrent = int(os.getenv("TRANS_MAX_CONCURRENCY", "3"))
        self.semaphore = asyncio.Semaphore(self.max_concurrent)

    def get_system_prompt(self, target_lang: str, file_type: str = "epub") -> str:
        base = [
            f"你是專業筆譯員。將輸入內容完整翻譯為 {target_lang}。",
            "規則：",
            "1) 僅翻譯可見文字；"
        ]
        if file_type == "epub":
            base[-1] += "保留所有 HTML 標籤與屬性不變（EPUB）。"
        else:
            base[-1] += "保持原有段落結構。"
        base += [
            "2) 不新增或刪除段落與內容。",
            "3) 公式、程式碼、數字、URL 不翻譯。",
            "4) 專有名詞譯法一致；若不確定以原文括號輔助。"
        ]
        if file_type == "epub":
            base.append("5) 對於 HTML 片段，請輸出對位的內容（僅變更文字，原標籤不動）。")
        return "\n".join(base)

    async def translate_text(
        self,
        text: str,
        target_lang: str,
        file_type: str = "epub",
        context: Optional[str] = None
    ) -> str:
        """單段翻譯，帶重試與『輸出未翻』偵測"""
        if not text or not text.strip():
            return text

        async with self.semaphore:
            for attempt in range(self.max_retries):
                try:
                    sys = self.get_system_prompt(target_lang, file_type)
                    user = f"請將下列內容翻譯為 {target_lang}：\n\n{text}"
                    
                    logger.info(f"Sending translation request to OpenAI (attempt {attempt+1})")
                    logger.debug(f"Input text: '{text[:200]}...{text[-50:] if len(text) > 200 else ''}'") 

                    resp = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": sys},
                            {"role": "user", "content": user}
                        ],
                        temperature=0.0,
                        max_tokens=4000,
                    )
                    out = (resp.choices[0].message.content or "").strip()
                    logger.info(f"Received OpenAI response, length: {len(out)}")
                    logger.debug(f"Output text: '{out[:200]}...{out[-50:] if len(out) > 200 else ''}'") 

                    # 若輸出與輸入極度相似（幾乎沒翻），則重試
                    if attempt < self.max_retries - 1:
                        same = out.replace(" ", "") == text.replace(" ", "")
                        # 粗略偵測：高比例 ASCII（英文）可能未翻
                        ascii_ratio = sum(c.isascii() for c in out) / max(1, len(out))
                        logger.debug(f"Translation check - same: {same}, ascii_ratio: {ascii_ratio:.2f}")
                        if same or ascii_ratio > 0.95:
                            logger.warning(f"Output looks unchanged/mostly ASCII (ratio: {ascii_ratio:.2f}); reinforcing and retrying.")
                            await asyncio.sleep(1.5 * (2 ** attempt))
                            continue

                    logger.info("Translation completed successfully")
                    return out

                except Exception as e:
                    if attempt < self.max_retries - 1:
                        wait = (2 ** attempt)
                        logger.warning(f"Translation attempt {attempt+1} failed: {e}. Retrying in {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        logger.error(f"Translation failed after {self.max_retries} attempts: {e}")
                        raise

    async def translate_batch(
        self,
        texts: List[str],
        target_lang: str,
        file_type: str = "epub",
        progress_callback=None
    ) -> List[str]:
        """批次翻譯（**保持原順序**）"""

        async def _task(ix: int, payload: str) -> Tuple[int, str]:
            try:
                out = await self.translate_text(payload, target_lang, file_type)
                return ix, out
            except Exception as e:
                logger.error(f"Failed to translate chunk {ix}: {e}")
                return ix, payload  # 失敗回傳原文，保持對位

        tasks = [asyncio.create_task(_task(i, t)) for i, t in enumerate(texts)]
        results: List[Tuple[int, str]] = []
        completed = 0

        for coro in asyncio.as_completed(tasks):
            ix, out = await coro
            results.append((ix, out))
            completed += 1
            if progress_callback:
                progress_callback(completed, len(texts))

        results.sort(key=lambda p: p[0])
        return [s for _, s in results]

    def chunk_text(self, text: str, max_chars: int = 3000) -> List[str]:
        """簡單切塊（必要時可換更聰明的切句器）"""
        if len(text) <= max_chars:
            return [text]

        chunks, buf = [], ""
        sentences = text.replace("\n\n", "\n<PARAGRAPH>\n").split("\n")

        for s in sentences:
            if s == "<PARAGRAPH>":
                if buf:
                    chunks.append(buf.strip()); buf = ""
                continue
            if len(buf) + len(s) + 1 > max_chars:
                if buf:
                    chunks.append(buf.strip()); buf = s + "\n"
                else:
                    chunks.append(s)
            else:
                buf += s + "\n"

        if buf:
            chunks.append(buf.strip())
        return chunks