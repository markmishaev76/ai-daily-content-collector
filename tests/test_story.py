from datetime import datetime, timezone

from src import story

NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)
TIERS = {"primary": ["datatracker.ietf.org", "openai.com", "aws.amazon.com/blogs/security"],
         "aggregator": ["hnrss.org", "news.ycombinator.com"]}
HN_SUMMARY = ("Article URL: https://example.com/post-2026-11\nComments URL: https://news.ycombinator.com/item?id=1\n"
              "Points: 120\n# Comments: 45")


def art(title, link=None, summary="", published=NOW, source="Src", feed="https://feeds.example.com/rss",
        image=None, section="S"):
    link = link if link is not None else "https://example.com/" + "".join(c for c in title.lower() if c.isalnum())
    return {"title": title, "link": link, "summary": summary, "published": published, "source": source,
            "feed": feed, "image": image, "section": section}


def test_hn_points_parsed():
    assert story.hn_points(HN_SUMMARY) == 165
    assert story.hn_points("Points: 7") == 7
    assert story.hn_points("A normal summary with 12 points") == 0
    assert story.hn_points(None) == 0


def test_ids_extracted_and_normalized():
    ids = story.extract_ids("Fix for cve-2026-109618 and RFC9700, see draft-ietf-oauth-foo-03")

    assert ids == {"CVE-2026-109618", "RFC 9700", "draft-ietf-oauth-foo"}
    assert story.extract_ids("rfc 6749 basics") == {"RFC 6749"}


def test_hn_boilerplate_has_no_ids_or_tokens():
    article = art("Show HN: a tool", summary=HN_SUMMARY)

    assert story.article_ids(article) == frozenset()
    assert story.title_tokens("The and of a to") == frozenset()


def test_title_tokens_normalized():
    assert story.title_tokens("Microsoft Patches: Exchange Zero-Days!") == {"microsoft", "patche", "exchange",
                                                                          "zero", "day"}


def test_hard_news_wording():
    hard = ["Exchange flaw CVE-2026-1234 exploited", "RFC 9700 published", "New draft-ietf-wimse-arch-01",
            "Kubernetes 1.35 released", "Retailer discloses data breach", "Zero-day actively exploited in Chrome"]
    soft = ["Thoughts on code review", "Why I moved to Rust in 2026", "Version control tips"]

    assert all(story.is_hard_news(art(t)) for t in hard)
    assert not any(story.is_hard_news(art(t)) for t in soft)


def test_source_tier():
    assert story.source_tier(art("a", link="https://datatracker.ietf.org/doc/x/"), TIERS) == "primary"
    assert story.source_tier(art("a", link="https://aws.amazon.com/blogs/security/x/"), TIERS) == "primary"
    assert story.source_tier(art("a", link="https://aws.amazon.com/blogs/aws/x/"), TIERS) == "normal"
    assert story.source_tier(art("a", link="https://example.com/x", feed="https://hnrss.org/newest?q=x"),
                             TIERS) == "aggregator"
    assert story.source_tier(art("a", link="https://openai.com/x", feed="https://hnrss.org/newest"),
                             TIERS) == "primary"
    assert story.source_tier(art("a", link="https://notopenai.com/x"), TIERS) == "normal"


def test_domain_strips_www():
    assert story.domain("https://www.Example.com/a") == "example.com"
    assert story.domain("not a url") == ""


FILLER = ["Rust 1.90 borrow checker deep dive", "Kubernetes gateway API patterns", "Postgres vacuum tuning guide",
          "Notes from a staff engineer offsite", "AI agent memory design notes", "Evaluating AI agent benchmarks",
          "MCP server registry launches", "AI agent observability with OpenTelemetry", "Why AI agents need budgets",
          "Hiring senior engineers in a downturn", "Terraform state locking explained", "Go generics one year on",
          "AI agent sandboxes compared", "Running MCP tools locally", "AI coding study from METR",
          "Grafana dashboards for SLOs", "Writing a design doc", "MCP auth spec changes", "AI agent cost controls",
          "Chrome extension supply chain attack"]


def pool(*titled):
    return [art(t) for t in FILLER] + list(titled)


def cluster_of(clusters, title):
    return next({a["title"] for a in c} for c in clusters if title in {a["title"] for a in c})


def test_title_tokens_keep_version_numbers():
    assert "1.35" in story.title_tokens("Kubernetes 1.35 released")


def test_paraphrased_headlines_cluster():
    a = art("Microsoft patches Exchange zero-day exploited in attacks", link="https://bleepingcomputer.com/1")
    b = art("Microsoft fixes actively exploited Exchange zero-day", link="https://thehackernews.com/2")
    c = art("Exchange Server zero-day patched by Microsoft", link="https://securityweek.com/3")

    clusters = story.cluster(pool(a, b, c))

    assert cluster_of(clusters, a["title"]) == {a["title"], b["title"], c["title"]}


def test_summary_sentence_links_paraphrases():
    a = art("PHP2Shell exploit attempts hit millions", link="https://thehackernews.com/1",
            summary="Attackers exploit the PHP2Shell RCE flaw in PHP to deploy Mirai malware. More.")
    b = art("Mirai botnet operators join the attacks", link="https://securityweek.com/2",
            summary="The PHP2Shell RCE flaw in PHP is now exploited by the Mirai botnet.")

    assert cluster_of(story.cluster(pool(a, b)), a["title"]) == {a["title"], b["title"]}


def test_feed_generic_words_ignored():
    assert story.title_tokens("AI agent has new LLM model using MCP") == {"mcp"}


def fooshell_core():
    return [art(f"Fooshell {w} CVE-2026-5555", link=f"https://{d}/1") for w, d in
            [("patched", "a.com"), ("mitigations", "b.com"), ("impact", "c.com")]]


def test_signature_word_pulls_in_follow_ups():
    follow = art("Fooshell puts services offline", link="https://d.com/2")
    other = art("Services offline after storm", link="https://e.com/3")

    clusters = story.cluster(pool(*fooshell_core(), follow, other))

    assert follow["title"] in cluster_of(clusters, "Fooshell patched CVE-2026-5555")
    assert cluster_of(clusters, other["title"]) == {other["title"]}


def test_signature_needs_three_domains():
    core = fooshell_core()[:2]
    follow = art("Fooshell puts services offline", link="https://d.com/2")

    assert cluster_of(story.cluster(pool(*core, follow)), follow["title"]) == {follow["title"]}


def test_widespread_word_is_not_a_signature():
    core = [art(f"Security {w} CVE-2026-5555", link=f"https://{d}/1") for w, d in
            [("patched", "a.com"), ("mitigations", "b.com"), ("impact", "c.com")]]
    common = [art(f"Security note {i}", link=f"https://n{i}.com/") for i in range(12)]

    clusters = story.cluster(pool(*core, *common))

    assert cluster_of(clusters, "Security note 0") == {"Security note 0"}


def test_same_cve_always_clusters():
    a = art("Critical Fortinet bug lets attackers in", summary="CVE-2026-109618 affects FortiOS. More text.")
    b = art("Patch now: CVE-2026-109618")

    clusters = story.cluster(pool(a, b))

    assert cluster_of(clusters, a["title"]) == {a["title"], b["title"]}


def test_same_draft_always_clusters():
    a = art("New version of draft-ietf-wimse-arch-07")
    b = art("WIMSE architecture update", summary="The draft-ietf-wimse-arch-08 revision adds tokens.")

    assert cluster_of(story.cluster(pool(a, b)), a["title"]) == {a["title"], b["title"]}


def test_unrelated_stay_apart():
    a = art("Microsoft patches Exchange zero-day exploited in attacks")
    b = art("Microsoft launches new Teams features")
    c = art("Exchange rates and the dollar")

    clusters = story.cluster(pool(a, b, c))

    assert cluster_of(clusters, a["title"]) == {a["title"]}
    assert all(len(c) == 1 for c in clusters)


def test_generic_words_do_not_cluster():
    a = art("Building secure AI agents with MCP")
    b = art("MCP security for AI agents")

    clusters = story.cluster(pool(a, b))

    assert cluster_of(clusters, a["title"]) == {a["title"]}


def test_coverage_counts_distinct_domains():
    members = [art("x", link="https://www.a.com/1"), art("y", link="https://a.com/2"), art("z", link="https://b.com/1")]

    assert story.coverage(members) == 2


def test_candidates_dedupe_keeps_first_section_and_max_hn():
    first = art("Same", link="https://example.com/same", summary="plain")
    dup = art("Same", link="https://example.com/same", summary="Points: 50\n# Comments: 10")
    feed = {"First": [first, art("Other", link="")], "Second": [dup, art("Two", link="javascript:x")]}

    cands = story.candidates(feed)

    assert [(c["title"], c["section"], c["hn"]) for c in cands] == [("Same", "First", 60)]
    assert first["section"] == "S" and "hn" not in first


def test_cluster_order_deterministic():
    items = pool(art("Patch now: CVE-2026-1"), art("CVE-2026-1 exploited"))

    assert story.cluster(items) == story.cluster(list(items))


CONFIG = {"topics": [{"name": "Eng", "weight": 1.5}, {"name": "Sec", "weight": 0.75}, {"name": "Other", "weight": 1.0}],
          "story": {"source_tiers": TIERS}}
HOURS = 3600


def at(hours):
    return datetime.fromtimestamp(NOW.timestamp() - hours * HOURS, tz=timezone.utc)


def winner(clusters, config=CONFIG, history=()):
    return story.score_clusters(clusters, config, list(history), NOW)[0].lead["title"]


def test_section_weight_changes_winner():
    a, b = art("Alpha story", section="Eng"), art("Beta story", section="Sec")
    swapped = dict(CONFIG, topics=[{"name": "Eng", "weight": 0.75}, {"name": "Sec", "weight": 1.5}])

    assert winner([[a], [b]]) == "Alpha story"
    assert winner([[a], [b]], swapped) == "Beta story"


def test_cluster_section_is_most_common_then_highest_weight():
    def section(*names):
        return story.score_clusters([[art(f"x{i}", section=n) for i, n in enumerate(names)]], CONFIG, [], NOW)[0]

    assert (section("Sec", "Sec", "Eng").section, section("Sec", "Sec", "Eng").section_weight) == ("Sec", 0.75)
    assert section("Sec", "Eng").section == "Eng"


def test_hn_boilerplate_earns_no_keyword_points():
    hn = art("Show HN: a tool", summary="Article URL: https://github.com/x/whatsapp-mcp\nPoints: 4\n# Comments: 0")

    assert story.score_clusters([[hn]], CONFIG, [], NOW)[0].keywords == 0


def test_freshness_changes_winner():
    def pair(age_a, age_b):
        return [[art("Alpha story", published=at(age_a))], [art("Beta story", published=at(age_b))]]

    assert winner(pair(1, 30)) == "Alpha story"
    assert winner(pair(30, 1)) == "Beta story"


def test_undated_cluster_assumed_mid_window():
    scored = story.score_clusters([[art("x", published=None)]], CONFIG, [], NOW)[0]

    assert scored.age_hours is None
    assert scored.freshness == story.freshness(story.UNDATED_AGE_HOURS)
    assert story.freshness(-5) == 1.0


def test_coverage_and_hn_points_add_to_base():
    members = [art("x", link="https://a.com/1"), art("x", link="https://b.com/1"), art("x", link="https://c.com/1")]
    members[0]["hn"] = 99

    scored = story.score_clusters([members], CONFIG, [], NOW)[0]

    assert scored.coverage == 3
    assert scored.coverage_pts == 2 * story.COVERAGE_PTS
    assert scored.hn_pts == story.HN_PTS * 2


def test_hard_news_bonus():
    a, b = art("Alpha story"), art("Beta story CVE-2026-0001")

    scored = {s.lead["title"]: s for s in story.score_clusters([[a], [b]], CONFIG, [], NOW)}

    assert scored["Beta story CVE-2026-0001"].hard_pts == story.HARD_NEWS_PTS
    assert scored["Alpha story"].hard_pts == 0
    assert winner([[a], [b]]) == "Beta story CVE-2026-0001"


def test_primary_tier_beats_aggregator():
    a = art("Alpha story", link="https://example.com/a", feed="https://hnrss.org/newest")
    b = art("Beta story", link="https://datatracker.ietf.org/doc/b/")

    assert winner([[a], [b]]) == "Beta story"


def test_novelty_penalizes_recent_section_and_story():
    a, b = art("Alpha story", section="Eng"), art("Beta story", section="Other")
    led_eng = {"date": "2026-10-22", "url": "https://elsewhere.com/x", "title": "x", "section": "Eng", "key_tokens": []}
    led_alpha = {"date": "2026-10-20", "url": a["link"], "title": "Alpha", "section": "Sec", "key_tokens": []}
    too_old = dict(led_alpha, date="2026-10-19")

    assert winner([[a], [b]]) == "Alpha story"
    assert story.score_clusters([[a]], CONFIG, [led_eng], NOW)[0].novelty == story.SECTION_REPEAT
    assert story.score_clusters([[a]], CONFIG, [led_alpha], NOW)[0].novelty == story.STORY_REPEAT
    assert story.score_clusters([[a]], CONFIG, [too_old], NOW)[0].novelty == 1.0
    assert winner([[a], [b]], history=[led_alpha]) == "Beta story"


def test_novelty_matches_key_tokens_and_ids():
    a = art("Exchange zero-day patched by Microsoft", section="Other")
    tokens = {"date": "2026-10-22", "url": "u", "title": "t", "section": "Sec",
              "key_tokens": ["exchange", "microsoft", "zero", "day", "server"]}
    ident = dict(tokens, key_tokens=["CVE-2026-0001"])
    b = art("Unrelated CVE-2026-0001 note", section="Other")

    assert story.score_clusters([[a]], CONFIG, [tokens], NOW)[0].novelty == story.STORY_REPEAT
    assert story.score_clusters([[b]], CONFIG, [ident], NOW)[0].novelty == story.STORY_REPEAT


def test_history_from_today_ignored():
    a = art("Alpha story", section="Eng")
    today = {"date": "2026-10-23", "url": a["link"], "title": "Alpha", "section": "Eng", "key_tokens": []}

    assert story.score_clusters([[a]], CONFIG, [today], NOW)[0].novelty == 1.0


def test_lead_member_prefers_image_then_primary():
    plain = art("Same story", link="https://datatracker.ietf.org/doc/x/")
    pic = art("Same story", link="https://example.com/x", image="https://img.example.com/x.jpg")

    assert story.score_clusters([[plain, pic]], CONFIG, [], NOW)[0].lead is pic
    assert story.score_clusters([[art("S", link="https://example.com/y"), plain]], CONFIG, [], NOW)[0].lead is plain


def test_deterministic_and_ties_break_on_title():
    clusters = [[art("Beta story")], [art("Alpha story")]]

    first = [s.lead["title"] for s in story.score_clusters(clusters, CONFIG, [], NOW)]

    assert first == ["Alpha story", "Beta story"]
    assert first == [s.lead["title"] for s in story.score_clusters(clusters[::-1], CONFIG, [], NOW)]
    assert "Alpha story" in story.score_clusters(clusters, CONFIG, [], NOW)[0].breakdown()


def test_invalid_weight_raises():
    bad = dict(CONFIG, topics=[{"name": "Eng", "weight": "high"}])

    import pytest
    with pytest.raises(ValueError, match="config.yaml"):
        story.score_clusters([[art("x", section="Eng")]], bad, [], NOW)


def feed_of(*articles):
    feed = {}
    for a in articles:
        feed.setdefault(a["section"], []).append({k: v for k, v in a.items() if k != "section"})
    return feed


def test_pick_story_uses_best_cluster_with_also_covered():
    a = art("Patch now: CVE-2026-109618", link="https://bleepingcomputer.com/1", section="Sec", published=at(2))
    b = art("Fortinet flaw CVE-2026-109618 exploited", link="https://thehackernews.com/2", section="Sec",
            published=at(5), image="https://img.example.com/b.jpg")
    c = art("CVE-2026-109618 advisory", link="https://www.thehackernews.com/3", section="Eng")
    other = art("Some essay", section="Eng", published=at(1))

    picked = story.pick_story(feed_of(a, b, c, other), CONFIG, [], None, NOW)

    assert picked.link == b["link"] and picked.image == b["image"]
    assert picked.section == "Sec" and picked.coverage == 2
    assert picked.ids == ["CVE-2026-109618"] and picked.age_hours == 0
    assert picked.also == [("bleepingcomputer.com", a["link"])]
    assert not picked.pinned and picked.scored[0].lead is not None


def test_empty_pool_no_story():
    assert story.pick_story({"Eng": []}, CONFIG, [], None, NOW) is None


def test_pinned_overrides():
    a = art("Big story CVE-2026-1", section="Eng")
    pinned_one = art("Quiet essay", link="https://essay.com/x/", section="Sec", published=at(40))
    pin = {"url": "https://essay.com/x", "title": "Read this one", "note": "My pick", "until": NOW.date()}

    picked = story.pick_story(feed_of(a, pinned_one), CONFIG, [], pin, NOW)

    assert picked.pinned and picked.link == "https://essay.com/x/"
    assert picked.title == "Read this one" and picked.note == "My pick" and picked.section == "Sec"


def test_pinned_outside_pool_uses_title_or_url():
    feed = feed_of(art("Big story", section="Eng"))
    pin = {"url": "https://essay.com/y", "title": None, "note": None, "until": NOW.date()}

    picked = story.pick_story(feed, CONFIG, [], pin, NOW)

    assert (picked.title, picked.link, picked.section, picked.image) == ("https://essay.com/y", pin["url"], None, None)
    assert picked.source == "essay.com" and picked.also == []
    assert story.pick_story({}, CONFIG, [], dict(pin, title="T"), NOW).title == "T"


def test_freshness_halves_in_twelve_hours():
    assert story.freshness(0) == 1.0
    assert story.freshness(12) == 0.5
    assert round(story.freshness(24), 3) == 0.333
