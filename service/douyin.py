
import re
from typing import Optional

from django.http import HttpResponse, HttpResponseServerError

from core.interface import Service
from core.model import Result, ErrorResult
from tools import store, analyzer, http_utils
from core import config
from core.type import Video

headers = {
    "user-agent": config.user_agent
}

download_headers = {
    "accept": "*/*",
    "accept-encoding": "identity;q=1, *;q=0",
    "accept-language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7,zh-TW;q=0.6,de;q=0.5,fr;q=0.4,ca;q=0.3,ga;q=0.2",
    "range": "bytes=0-",
    "sec-fetch-dest": "video",
    "sec-fetch-mode": "no-cors",
    "sec-fetch-site": "cross-sit",
    "user-agent": config.user_agent
}

vtype = Video.DOUYIN


class DouyinService(Service):

    @classmethod
    def fetch(cls, url: str, model=0) -> Result:
        """
        获取视频详情
        :param url:
        :param model:
        :return:
        """
        url = analyzer.get_url(vtype, url)
        if url is None:
            return ErrorResult.URL_NOT_INCORRECT

        # 请求短链接，获得itemId和dytk
        res = http_utils.get(url, header=headers)
        if http_utils.is_error(res):
            return Result.error(res)

        html = str(res.content)
        try:
            item_id = re.findall(r"(?<=itemId:\s\")\d+", html)[0]
            dytk = re.findall(r"(?<=dytk:\s\")(.*?)(?=\")", html)[0]
        except IndexError:
            return Result.failed(res.reason)

        # 组装视频长链接
        infourl = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids=" + item_id + "&dytk=" + dytk

        # 请求长链接，获取play_addr
        url_res = http_utils.get(infourl, header=headers)
        if http_utils.is_error(url_res):
            return Result.error(url_res)

        vhtml = str(url_res.text)
        try:
            uri = re.findall(r'(?<=\"uri\":\")\w{32}(?=\")', vhtml)[0]
        except IndexError:
            return Result.failed(url_res.reason)
        if not uri:
            return ErrorResult.VIDEO_ADDRESS_NOT_FOUNT

        link = "https://aweme.snssdk.com/aweme/v1/play/?video_id=" + uri + \
                "&line=0&ratio=540p&media_type=4&vr_type=0&improve_bitrate=0" \
                "&is_play_url=1&is_support_h265=0&source=PackSourceEnum_PUBLISH"
        result = Result.success(link)

        if model != 0:
            result.ref = res.url
        return result

    @classmethod
    def download(cls, url) -> HttpResponse:
        """
        下载视频
        :param url:
        :return:
        """
        # 检查文件
        index = cls.index(url)
        file = store.find(vtype, index)
        if file is not None:
            return Service.stream(file, index)

        result = cls.fetch(url, model=1)
        if not result.is_success():
            return HttpResponseServerError(result.get_data())

        dheaders = download_headers.copy()
        dheaders['referer'] = result.ref

        res = http_utils.get(url=result.get_data(), header=dheaders)
        if http_utils.is_error(res):
            return HttpResponseServerError(str(res))

        store.save(vtype, res, index)
        res.close()

        file = store.find(vtype, index)
        return Service.stream(file, index)


if __name__ == '__main__':
    DouyinService.fetch('https://v.douyin.com/cCBrrq/')
