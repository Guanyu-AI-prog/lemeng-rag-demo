"""流式 /ask/stream 测试:事件流完整性 + 首字延迟(TTFT)+ 缓存命中"""
import json
import sys
import time
import urllib.request

BASE = "http://localhost:8001"


def stream_ask(question, mode="auto"):
    req = urllib.request.Request(
        f"{BASE}/ask/stream",
        data=json.dumps({"question": question, "mode": mode}).encode(),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    ttft = None
    route, cached, done_elapsed, deltas, chars = None, False, None, 0, 0
    events = []
    with urllib.request.urlopen(req, timeout=300) as resp:
        event = None
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
                events.append(event)
            elif line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1].strip())
                if event == "meta":
                    route, cached = data["route"], data["cached"]
                elif event == "delta":
                    if ttft is None:
                        ttft = time.time() - t0
                    deltas += 1
                    chars += len(data["text"])
                elif event == "done":
                    done_elapsed = data["elapsed"]
    return {"route": route, "cached": cached, "ttft": round(ttft or -1, 2),
            "total": round(time.time() - t0, 2), "server_elapsed": done_elapsed,
            "deltas": deltas, "chars": chars, "events_ok":
            events[0] == "meta" and events[-1] == "done"}


print("== faq 第一次(建缓存)==")
print(stream_ask("星芽的课包是怎么收费的?"))

print("\n== faq 第二次(应秒回缓存)==")
print(stream_ask("星芽的课包是怎么收费的?"))

print("\n== faq 相似问法(归一化键命中)==")
print(stream_ask("星芽课包怎么收费"))

print("\n== talk 流式(重点看 TTFT)==")
print(stream_ask("家长觉得编程课太贵了,不如报英语数学,怎么回复?", mode="talk"))
