"""
小红书 API 客户端
参考 temp.py 和 MediaCrawler 实现
用于调用小红书官方 API 获取笔记详情、视频 URL 等
"""
import asyncio
import json
import random
import base64
from typing import Any, Dict, Union
from urllib.parse import urlencode

import httpx
from playwright.async_api import BrowserContext, Page
from tenacity import retry, stop_after_attempt, wait_fixed
from httpx import RequestError


# === 异常类 ===

class DataFetchError(RequestError):
    """数据获取失败"""
    pass


class IPBlockError(RequestError):
    """IP 被封禁（请求过快）"""
    pass


# === 签名相关函数 ===

def get_b3_trace_id():
    """生成 x-b3-traceid"""
    chars = "abcdef0123456789"
    return ''.join(random.choice(chars) for _ in range(16))


def sign(a1="", b1="", x_s="", x_t=""):
    """
    生成请求签名

    Args:
        a1: cookie 中的 a1 值
        b1: localStorage 中的 b1 值
        x_s: 从 window._webmsxyw 获取的 X-s
        x_t: 从 window._webmsxyw 获取的 X-t

    Returns:
        Dict: 包含签名的字典 {x-s, x-t, x-s-common, x-b3-traceid}
    """
    common = {
        "s0": 3,  # getPlatformCode
        "s1": "",
        "x0": "1",  # localStorage.getItem("b1b1")
        "x1": "3.7.8-2",  # version
        "x2": "Mac OS",
        "x3": "xhs-pc-web",
        "x4": "4.37.2",
        "x5": a1,  # cookie a1
        "x6": x_t,
        "x7": x_s,
        "x8": b1,  # localStorage b1
        "x9": "",
        "x10": "",
    }
    x_s_common = base64.b64encode(json.dumps(common, separators=(',', ':')).encode()).decode()
    x_b3_traceid = get_b3_trace_id()

    return {
        "x-s": x_s,
        "x-t": x_t,
        "x-s-common": x_s_common,
        "x-b3-traceid": x_b3_traceid
    }


# === API 客户端 ===

class XiaoHongShuClient:
    """
    小红书 API 客户端
    用于调用小红书官方 API，获取笔记详情、视频 URL 等
    """

    def __init__(
        self,
        timeout: int = 60,
        proxy: str = None,
        *,
        headers: Dict[str, str],
        playwright_page: Page,
        cookie_dict: Dict[str, str],
    ):
        """
        初始化客户端

        Args:
            timeout: 请求超时时间（秒）
            proxy: 代理地址（可选）
            headers: 请求头字典
            playwright_page: Playwright Page 对象（用于调用 JS 签名函数）
            cookie_dict: Cookie 字典
        """
        self.proxy = proxy
        self.timeout = timeout
        self.headers = headers
        self._host = "https://edith.xiaohongshu.com"
        self._domain = "https://www.xiaohongshu.com"
        self.IP_ERROR_STR = "网络连接异常，请检查网络设置或重启试试"
        self.IP_ERROR_CODE = 300012
        self.NOTE_ABNORMAL_STR = "笔记状态异常，请稍后查看"
        self.NOTE_ABNORMAL_CODE = -510001
        self.playwright_page = playwright_page
        self.cookie_dict = cookie_dict

    async def _pre_headers(self, url: str, data=None) -> Dict:
        """
        请求头参数签名
        调用页面中的 window._webmsxyw 函数生成签名

        Args:
            url: 请求 URL
            data: 请求体数据（POST 时使用）

        Returns:
            Dict: 包含签名的完整请求头
        """
        # 调用浏览器中的签名函数
        encrypt_params = await self.playwright_page.evaluate(
            "([url, data]) => window._webmsxyw(url, data)", [url, data]
        )

        # 获取 localStorage 中的 b1
        local_storage = await self.playwright_page.evaluate("() => window.localStorage")

        # 生成签名
        signs = sign(
            a1=self.cookie_dict.get("a1", ""),
            b1=local_storage.get("b1", ""),
            x_s=encrypt_params.get("X-s", ""),
            x_t=str(encrypt_params.get("X-t", "")),
        )

        # 更新请求头
        headers = {
            "X-S": signs["x-s"],
            "X-T": signs["x-t"],
            "x-S-Common": signs["x-s-common"],
            "X-B3-Traceid": signs["x-b3-traceid"],
        }
        self.headers.update(headers)
        return self.headers

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def request(self, method: str, url: str, **kwargs) -> Union[str, Any]:
        """
        封装 httpx 的公共请求方法
        支持自动重试（最多3次，间隔1秒）

        Args:
            method: 请求方法（GET/POST）
            url: 请求 URL
            **kwargs: 其他请求参数

        Returns:
            Dict 或 str: 响应数据

        Raises:
            IPBlockError: IP 被封禁
            DataFetchError: 数据获取失败
        """
        return_response = kwargs.pop("return_response", False)

        async with httpx.AsyncClient(proxy=self.proxy) as client:
            response = await client.request(method, url, timeout=self.timeout, **kwargs)

        # 检查验证码
        if response.status_code in (471, 461):
            verify_type = response.headers.get("Verifytype", "unknown")
            verify_uuid = response.headers.get("Verifyuuid", "unknown")
            msg = f"出现验证码，请求失败，Verifytype: {verify_type}，Verifyuuid: {verify_uuid}"
            raise Exception(msg)

        # 返回原始文本
        if return_response:
            return response.text

        # 解析 JSON
        data: Dict = response.json()
        if data.get("success"):
            return data.get("data", data.get("success", {}))
        elif data.get("code") == self.IP_ERROR_CODE:
            raise IPBlockError(self.IP_ERROR_STR)
        else:
            raise DataFetchError(data.get("msg", "未知错误"))

    async def get(self, uri: str, params=None) -> Dict:
        """
        GET 请求（自动签名）

        Args:
            uri: 请求路径（相对于 _host）
            params: URL 参数字典

        Returns:
            Dict: 响应数据
        """
        final_uri = uri
        if isinstance(params, dict):
            final_uri = f"{uri}?{urlencode(params)}"

        headers = await self._pre_headers(final_uri)
        return await self.request(
            method="GET",
            url=f"{self._host}{final_uri}",
            headers=headers
        )

    async def post(self, uri: str, data: dict, **kwargs) -> Dict:
        """
        POST 请求（自动签名）

        Args:
            uri: 请求路径（相对于 _host）
            data: 请求体数据字典

        Returns:
            Dict: 响应数据
        """
        headers = await self._pre_headers(uri, data)
        json_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        return await self.request(
            method="POST",
            url=f"{self._host}{uri}",
            data=json_str,
            headers=headers,
            **kwargs,
        )

    async def get_note_by_id(
        self,
        note_id: str,
        xsec_source: str = "",
        xsec_token: str = "",
    ) -> Dict:
        """
        获取笔记详情

        Args:
            note_id: 笔记 ID
            xsec_source: 渠道来源（默认 pc_feed）
            xsec_token: 验证 token（可选）

        Returns:
            Dict: 笔记详情（包含 title, type, video, image_list 等）
                 返回空字典表示获取失败
        """
        if not xsec_source:
            xsec_source = "pc_feed"

        data = {
            "source_note_id": note_id,
            "image_formats": ["jpg", "webp", "avif"],
            "extra": {"need_body_topic": 1},
            "xsec_source": xsec_source,
            "xsec_token": xsec_token,
        }
        uri = "/api/sns/web/v1/feed"

        try:
            res = await self.post(uri, data)
            if res and res.get("items"):
                note_card: Dict = res["items"][0]["note_card"]
                return note_card
            return {}
        except Exception as e:
            # 记录错误但不抛出，返回空字典
            print(f"[XiaoHongShuClient] 获取笔记 {note_id} 失败: {e}")
            return {}

    async def update_cookies(self, browser_context: BrowserContext):
        """
        更新 cookies（登录成功后调用）

        Args:
            browser_context: 浏览器上下文对象
        """
        cookies = await browser_context.cookies()
        cookie_dict = {c['name']: c['value'] for c in cookies}
        cookie_str = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])

        self.headers["Cookie"] = cookie_str
        self.cookie_dict = cookie_dict
