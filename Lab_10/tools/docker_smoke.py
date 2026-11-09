"""Exercise the real Docker image, non-root runtime, env, health and volume restart."""

from pathlib import Path
import json
import subprocess
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def command(*arguments):
    return subprocess.run(
        ["docker", *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def main():
    image = "book-catalog:ci"
    suffix = uuid.uuid4().hex[:10]
    name = f"book-catalog-lab10-{suffix}"
    volume = f"book-catalog-lab10-data-{suffix}"
    output = ROOT / "docs/results"
    output.mkdir(parents=True, exist_ok=True)
    logs = []
    command("volume", "create", volume)

    def start():
        command(
            "run",
            "--detach",
            "--name",
            name,
            "--publish",
            "127.0.0.1::8000",
            "--env",
            "APP_ENV=production",
            "--env",
            "LOG_LEVEL=DEBUG",
            "--env",
            "DATABASE_URL=sqlite:////app/data/library.db",
            "--volume",
            f"{volume}:/app/data",
            image,
        )
        port = command("port", name, "8000/tcp").splitlines()[0].rsplit(":", 1)[1]
        base = f"http://127.0.0.1:{port}"
        for _ in range(120):
            try:
                with urllib.request.urlopen(base + "/health", timeout=2) as response:
                    health = json.load(response)
                if (
                    command("inspect", "--format", "{{.State.Health.Status}}", name)
                    == "healthy"
                ):
                    assert health["environment"] == "production"
                    return base, health
            except (OSError, ValueError):
                pass
            time.sleep(0.5)
        raise RuntimeError("Container did not become healthy")

    def request(base, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        with urllib.request.urlopen(
            urllib.request.Request(
                base + path,
                data=data,
                method=method,
                headers={"Content-Type": "application/json"},
            ),
            timeout=10,
        ) as response:
            return response.status, json.load(response)

    try:
        base, health = start()
        _, author = request(base, "POST", "/authors", {"name": "Іван Франко"})
        status, book = request(
            base,
            "POST",
            "/books",
            {
                "title": "Захар Беркут",
                "author_id": author["id"],
                "year": 1883,
                "pages": 192,
            },
        )
        assert status == 201
        _, statistics = request(base, "GET", "/books/statistics")
        assert statistics["average_pages"] == 192
        with urllib.request.urlopen(base + "/docs") as response:
            assert response.status == 200
        assert command("exec", name, "id", "-u") == "10001"
        state = json.loads(command("inspect", name))[0]
        image_data = json.loads(command("image", "inspect", image))[0]
        proof = dict(
            status="PASS",
            image=image,
            image_id=image_data["Id"],
            image_size_bytes=image_data["Size"],
            configured_user=image_data["Config"]["User"],
            environment=[
                e
                for e in state["Config"]["Env"]
                if e.startswith(("APP_ENV=", "LOG_LEVEL=", "DATABASE_URL="))
            ],
            health=health,
            container_state=state["State"]["Status"],
            docker_health=state["State"]["Health"]["Status"],
            docker_ps=command("ps", "--filter", f"name={name}"),
            docker_images=command("images", image),
            created_book=book,
            statistics=statistics,
        )
        logs.append(command("logs", name))
        command("rm", "--force", name)
        base, restarted_health = start()
        _, books = request(base, "GET", "/books")
        assert len(books) == 1 and books[0]["title"] == book["title"]
        proof["volume_restart_persistence"] = "PASS"
        proof["restarted_health"] = restarted_health
        logs.append(command("logs", name))
        (output / "docker.json").write_text(
            json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "docker.log").write_text("\n".join(logs), encoding="utf-8")
        print(json.dumps(proof, ensure_ascii=False, indent=2))
    finally:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True)
        subprocess.run(["docker", "volume", "rm", volume], capture_output=True)


if __name__ == "__main__":
    main()
