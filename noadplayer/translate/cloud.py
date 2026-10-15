"""온라인 번역 — 사용자 본인 API 키로 DeepL·Google·Microsoft 를 부른다 (개발자 쪽 비용 없음)."""
import json
import urllib.error
import urllib.parse
import urllib.request

from ..stt.download import Cancelled


class CloudError(RuntimeError):
    pass


def _post(url, body, headers, service):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise CloudError(_explain(service, e.code, detail)) from e
    except urllib.error.URLError as e:
        raise CloudError(f"{service}에 연결하지 못했습니다: {e.reason}") from e


def _explain(service, code, detail):
    if code in (401, 403):
        msg = "API 키가 틀렸거나 권한이 없습니다. '번역 설정'에서 키를 확인하세요."
    elif code in (429,):
        msg = "요청이 너무 많습니다. 잠시 뒤 다시 시도하세요."
    elif code == 456 or "quota" in detail.lower():
        msg = "이번 달 무료 한도를 다 썼습니다."
    else:
        msg = "번역 요청이 실패했습니다."
    return f"{service}: {msg} (오류 {code})\n{detail}"


class _Cloud:
    name = ""
    chunk = 50

    def __init__(self, key, region=""):
        if not key:
            raise CloudError(f"{self.name} API 키가 없습니다. '번역 설정'에서 넣어 주세요.")
        self.key = key
        self.region = region
        self.device = "온라인"

    def start(self, cancelled=lambda: False):
        pass

    def close(self):
        pass

    def translate(self, lines, progress=lambda done, total: None, cancelled=lambda: False):
        out = []
        for i in range(0, len(lines), self.chunk):
            if cancelled():
                raise Cancelled()
            res = self._call(lines[i:i + self.chunk])
            if len(res) != len(lines[i:i + self.chunk]):
                raise CloudError(f"{self.name}: 돌려받은 줄 수가 맞지 않습니다.")
            out += res
            progress(len(out), len(lines))
        return out


class DeepL(_Cloud):
    name = "DeepL"
    chunk = 50

    def _call(self, texts):
        host = "api-free.deepl.com" if self.key.endswith(":fx") else "api.deepl.com"   # 무료 키는 :fx 로 끝남
        d = _post(f"https://{host}/v2/translate", {"text": texts, "target_lang": "KO"},
                  {"Authorization": f"DeepL-Auth-Key {self.key}"}, self.name)
        return [t["text"] for t in d["translations"]]


class Google(_Cloud):
    name = "Google"
    chunk = 100

    def _call(self, texts):
        url = "https://translation.googleapis.com/language/translate/v2?key=" + urllib.parse.quote(self.key)
        d = _post(url, {"q": texts, "target": "ko", "format": "text"}, {}, self.name)
        return [t["translatedText"] for t in d["data"]["translations"]]


class Azure(_Cloud):
    name = "Microsoft"
    chunk = 100

    def _call(self, texts):
        headers = {"Ocp-Apim-Subscription-Key": self.key}
        if self.region:
            headers["Ocp-Apim-Subscription-Region"] = self.region
        d = _post("https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&to=ko",
                  [{"Text": t} for t in texts], headers, self.name)
        return [x["translations"][0]["text"] for x in d]
