import json
import os
import shutil

import fire
import vuddy_util
from joblib import Parallel, delayed
from loguru import logger

VUDDY_RESULT_DIR = "./vuddy-result"
VUDDY_EXPLODED_DIR = "./vuddy-exploded"


def clean(label, version):
    output = f"{VUDDY_RESULT_DIR}/vuddy_{label}_{vuddy_util.escape(version)}.jsonl"
    if os.path.exists(output):
        os.unlink(output)

    exploded = f"{VUDDY_EXPLODED_DIR}/{label}_{vuddy_util.escape(version)}/"
    if os.path.exists(exploded):
        shutil.rmtree(exploded)


def run_vuddy(label, src_path, version):
    output = f"{VUDDY_RESULT_DIR}/vuddy_{label}_{vuddy_util.escape(version)}.jsonl"
    if os.path.exists(output):
        return

    exploded = f"{VUDDY_EXPLODED_DIR}/{label}_{vuddy_util.escape(version)}/"
    if not os.path.exists(exploded):
        with vuddy_util.TempRepo(src_path, version) as src_clone:
            vuddy_util.explode(src_clone, exploded)

    basename = os.path.basename(exploded.rstrip("/"))
    hidx = os.path.join(exploded, "hidx", f"hashmark_4_{basename}.hidx")
    if not os.path.exists(hidx):
        ret, param = vuddy_util.run_hmark(exploded)
        if ret != 0:
            logger.info(f"error in {src_path}: {ret} {param}")
            return -1

        vuddy_util.patch_hidx(hidx)

    res, params = vuddy_util.upload_hidx(hidx)
    if res != 0:
        resp = params
        logger.info(f"error in {label}: {res} {resp.request.url} {resp.status_code}")  # type: ignore
        return -2
    tree_result = params["result"]  # type: ignore
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as f:
        for entry in tree_result:
            json.dump(entry, f)
            f.write("\n")


def run_all(projects):
    Parallel()(
        delayed(run_vuddy)(row["label"], row["project_dir"], row["version"])
        for row in projects
    )


if __name__ == "__main__":
    fire.Fire()
