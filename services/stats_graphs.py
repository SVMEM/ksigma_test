import io
import matplotlib.pyplot as plt

def bar_topics_png(pairs: list[tuple[str, int]]) -> bytes:
    # pairs: [(topic, count), ...]
    topics = [p[0] for p in pairs]
    counts = [p[1] for p in pairs]

    fig = plt.figure()
    plt.bar(topics, counts)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
