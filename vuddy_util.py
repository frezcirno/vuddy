import json
import os
import re
import shutil
import subprocess as sp
import tempfile
import time
from typing import List, Union

import codeparser
import git
import linguist
import requests
import timeout_decorator
from git import Repo

HMARK = os.path.abspath("./hmark_4.0.1_linux_x64")


def escape(s):
    return s.replace("/", "_")


def traverse_files(dir_path=".", relative=False):
    for root, _, files in os.walk(dir_path):
        for file in files:
            if relative:
                yield os.path.relpath(os.path.join(root, file), dir_path)
            else:
                yield os.path.join(root, file)


def traverse_src_files(
    dir_path: str,
    langs: Union[str, List[str]],
    relative: bool = False,
):
    if isinstance(langs, str):
        langs = [langs]
    for file in traverse_files(dir_path, relative):
        lang = linguist.detect_language(os.path.join(dir_path, file))
        if lang in langs:
            yield file, lang


def explode(src_path, output):
    for rel_path, lang in traverse_src_files(
        src_path, ["C", "C++", "Java"], relative=True
    ):
        with open(src_path + "/" + rel_path, "rb") as f_src:
            file_content = f_src.read()

        try:
            funcs = codeparser.extract_functions(file_content, lang, timeout=10)
        except timeout_decorator.TimeoutError:
            print("Timeout when parsing", rel_path)
            continue

        file_ext = os.path.splitext(rel_path)[1]
        output_path = os.path.join(output, rel_path)
        os.makedirs(output_path, exist_ok=True)

        for func in funcs:
            func_output_path = f"{output_path}/{func.start_line}{file_ext}"
            with open(func_output_path, "wb") as f_func:
                f_func.write(func.code_bytes)


class TempRepo:
    def __init__(self, src_path, version):
        self.src_path = src_path
        self.version = version

    @staticmethod
    def clean_checkout(repo, rev, clean=True):
        if clean:
            try:
                repo.git.restore("--staged", ".")
                repo.git.restore(".")
                repo.git.clean("-dfx")
            except git.GitCommandError:
                pass
        repo.git.checkout(rev)
        assert repo.commit(rev).hexsha == repo.head.commit.hexsha, "checkout failed"

    def __enter__(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        target_path = os.path.join(self.tmpdir.name, "repo")
        shutil.copytree(self.src_path, target_path, symlinks=True)
        TempRepo.clean_checkout(Repo(target_path), self.version)
        return target_path

    def __exit__(self, exc_type, exc_value, traceback):
        self.tmpdir.cleanup()


def run_hmark(target_dir):
    out = tempfile.NamedTemporaryFile(delete=False)
    err = tempfile.NamedTemporaryFile(delete=False)
    target_dir = os.path.abspath(target_dir)
    ret = sp.call(
        f"{HMARK} -n -c {target_dir} ON",
        shell=True,
        cwd=target_dir,
        stdout=out,
        stderr=err,
    )
    if ret == 0:
        os.remove(out.name)
        os.remove(err.name)

    return ret, (out.name, err.name)


def patch_hidx(hidx):
    with open(hidx) as f:
        original = f.readlines()

    hmarks = eval(original[1])
    for entry in hmarks:
        original_file = entry["file"]
        original_file0, original_file1 = original_file.rsplit("/", 1)
        original_file0 = original_file0.replace(".", "#")
        entry["file"] = original_file0 + "/" + original_file1

    with open(hidx, "w") as f:
        f.write(original[0])
        f.write(str(hmarks))


def upload_hidx(hidx):
    sess = requests.Session()

    resp = sess.get(
        "https://iotcube.net/process/type?processType=wf1",
        headers={
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://iotcube.net",
            "Referer": "https://iotcube.net/process/type/wf1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    )
    if resp.status_code != 200:
        return resp.status_code, resp

    pattern = r'<meta name="csrf-token" content="([^"]+)"'
    match = re.search(pattern, resp.text)
    if not match:
        return -1, resp
    csrf_token = match.group(1)

    # upload
    with open(hidx, "rb") as f:
        basename = os.path.basename(hidx)
        resp = sess.post(
            "https://iotcube.net/process/upload/wf1",
            headers={
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Origin": "https://iotcube.net",
                "Referer": "https://iotcube.net/process/type/wf1",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "X-CSRF-TOKEN": csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
            data={"_token": csrf_token},
            files={"wf1file": (basename, f)},
        )
    if resp.status_code != 200:
        return resp.status_code, resp

    # start
    resp = sess.post(
        "https://iotcube.net/process/start/wf1",
        headers={
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://iotcube.net",
            "Referer": "https://iotcube.net/process/type/wf1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "X-Csrf-Token": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    )
    if resp.status_code != 200:
        return resp.status_code, resp
    vul_file = resp.json()["file"]

    # progress
    for _ in range(10):
        resp = sess.post(
            "https://iotcube.net/process/progress/wf1",
            headers={
                "Accept": "application/json",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Origin": "https://iotcube.net",
                "Referer": "https://iotcube.net/process/type/wf1",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "X-Csrf-Token": csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
        )
        if resp.status_code != 200:
            return resp.status_code, resp
        if resp.json()["progress"] == 100:
            break
        time.sleep(1)

    # Get result page
    resp = sess.get(
        f"https://iotcube.net/process/report/wf1/{vul_file}",
        headers={
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Origin": "https://iotcube.net",
            "Referer": "https://iotcube.net/process/type/wf1",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "X-Csrf-Token": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    )
    if resp.status_code != 200:
        return resp.status_code, resp

    pattern = r"var objResult = JSON.parse\('(.*)'\);"
    match = re.search(pattern, resp.text)
    if not match:
        return -2, resp
    objResult = json.loads(match.group(1))

    # walk tree
    tree_json = objResult["tree_json"]
    stack = [tree_json]
    tree_result = []
    while stack:
        node = stack.pop()
        if "text" in node:
            # leaf node
            textsplit = node["text"].split("::", 5)
            _, file_path, _, vul_id, fname, _ = textsplit
            # redis##redis
            vul_proj, vul_id = vul_id.split("/", 1)
            # fork_create_OLD.vul
            vul_file, vul_id_func = vul_id.split("@@", 1)
            # CVE-2022-33105
            # 5.0
            # CWE-401
            # 586a16ad7907d9742a63cfcec464be7ac54aa495
            # fork.c
            cve_id, score, cwe_id, commit_id, vul_fname = vul_file.split("_", 4)

            tree_result.append(
                {
                    "file_path": file_path,
                    "vul_proj": vul_proj,
                    "cve_id": cve_id,
                    "score": score,
                    "cwe_id": cwe_id,
                    "commit_id": commit_id,
                    "vul_fname": vul_fname,
                    "vul_id_func": vul_id_func,
                }
            )
        else:
            # non-leaf node
            for child in node["children"]:
                stack.append(child)

    # Download rawdata
    # resp = sess.get(
    #     f"https://iotcube.net/process/report_rawdata/wf1/{vul_file}",
    #     headers={
    #         "Accept": "application/json",
    #         "Accept-Language": "zh-CN,zh;q=0.9",
    #         "Cache-Control": "no-cache",
    #         "Connection": "keep-alive",
    #         "Origin": "https://iotcube.net",
    #         "Referer": "https://iotcube.net/process/type/wf1",
    #         "Sec-Fetch-Dest": "empty",
    #         "Sec-Fetch-Mode": "cors",
    #         "Sec-Fetch-Site": "same-origin",
    #         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    #         "X-Requested-With": "XMLHttpRequest",
    #         "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
    #         "sec-ch-ua-mobile": "?0",
    #         "sec-ch-ua-platform": '"Windows"',
    #     },
    # )
    # if resp.status_code != 200:
    #     return resp.status_code, resp

    return 0, {
        # "rawData": json.loads(resp.text),
        # "objResult": objResult
        "result": tree_result,
    }
