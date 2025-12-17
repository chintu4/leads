try:
    from ddgs import DDGS
except Exception:
    # Older package name compat
    from duckduckgo_search import DDGS


def duck(query):
    with DDGS() as ddgs:
        results = ddgs.text(query)
        return list(results)


if __name__ == "__main__":
    # Example usage when run as a script
    print(duck("hello"))