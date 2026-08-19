from ado_api.tags import (
    DEPLOYMENT_TAG_PREFIXES,
    TAG_PR_RE,
    TAG_PROD_RE,
    TAG_STAGE_RE,
    format_commit_tag,
    format_pr_tag,
    parse_tags_to_dict,
    pr_tag_variants,
)


class TestTagRegexes:
    def test_stage_hyphen(self):
        assert TAG_STAGE_RE.match("stage-2026-07-24T15:09:07")

    def test_stage_equals(self):
        assert TAG_STAGE_RE.match("stage=2026-07-24T15:09:07")

    def test_prod_hyphen(self):
        assert TAG_PROD_RE.match("prod-2026-07-24T15:09:07")

    def test_prod_equals(self):
        assert TAG_PROD_RE.match("prod=2026-07-24T15:09:07")

    def test_pr_legacy(self):
        m = TAG_PR_RE.match("PR-49730")
        assert m and m.group(1) == "49730"

    def test_pr_new(self):
        m = TAG_PR_RE.match("pr=49730")
        assert m and m.group(1) == "49730"

    def test_stage_no_match_garbage(self):
        assert not TAG_STAGE_RE.match("stage-notadatetime")

    def test_deployment_prefixes_cover_both_formats(self):
        assert "stage-" in DEPLOYMENT_TAG_PREFIXES
        assert "stage=" in DEPLOYMENT_TAG_PREFIXES
        assert "prod-" in DEPLOYMENT_TAG_PREFIXES
        assert "prod=" in DEPLOYMENT_TAG_PREFIXES


class TestParseTagsToDict:
    def test_key_value_format(self):
        result = parse_tags_to_dict(["branch=master", "pipeline=dbx_pipeline_claims"])
        assert result == {"branch": "master", "pipeline": "dbx_pipeline_claims"}

    def test_legacy_pr_format(self):
        assert parse_tags_to_dict(["PR-49730"]) == {"pr": "49730"}

    def test_legacy_env_timestamp_format(self):
        result = parse_tags_to_dict(
            ["dev-2026-07-24T15:09:07", "stage-2026-07-24T15:09:12"]
        )
        assert result == {"dev": "2026-07-24T15:09:07", "stage": "2026-07-24T15:09:12"}

    def test_bare_commit_hash(self):
        assert parse_tags_to_dict(["27eba981"]) == {"commit": "27eba981"}

    def test_full_realistic_tag_set(self):
        tags = [
            "requestedfor=Jessica Smith",
            "pipeline=dbx_pipeline_payer_billing",
            "branch=master",
            "27eba981",
            "PR-49730",
            "dev-2026-07-24T15:09:07",
            "stage-2026-07-24T15:09:12",
        ]
        result = parse_tags_to_dict(tags)
        assert result == {
            "requestedfor": "Jessica Smith",
            "pipeline": "dbx_pipeline_payer_billing",
            "branch": "master",
            "commit": "27eba981",
            "pr": "49730",
            "dev": "2026-07-24T15:09:07",
            "stage": "2026-07-24T15:09:12",
        }

    def test_new_format_all_key_value(self):
        tags = [
            "commit=27eba981",
            "pr=49730",
            "dev=2026-07-24T15:09:07",
            "stage=2026-07-24T15:09:12",
        ]
        result = parse_tags_to_dict(tags)
        assert result == {
            "commit": "27eba981",
            "pr": "49730",
            "dev": "2026-07-24T15:09:07",
            "stage": "2026-07-24T15:09:12",
        }

    def test_empty_tags(self):
        assert parse_tags_to_dict([]) == {}

    def test_key_value_with_equals_in_value(self):
        assert parse_tags_to_dict(["description=a=b=c"]) == {"description": "a=b=c"}


class TestFormatTagFunctions:
    def test_format_commit_tag(self):
        assert format_commit_tag("27eba981") == "commit=27eba981"

    def test_format_pr_tag_with_str(self):
        assert format_pr_tag("49846") == "pr=49846"

    def test_format_pr_tag_with_int(self):
        assert format_pr_tag(49846) == "pr=49846"

    def test_format_tags_round_trip_through_parser(self):
        """format_*_tag output must be exactly what parse_tags_to_dict and the *_RE
        regexes expect — these three are the producer/parser contract for the same format."""
        commit_tag = format_commit_tag("27eba981")
        pr_tag = format_pr_tag(49846)

        assert parse_tags_to_dict([commit_tag, pr_tag]) == {
            "commit": "27eba981",
            "pr": "49846",
        }
        assert TAG_PR_RE.match(pr_tag)


class TestPrTagVariants:
    def test_bare_id(self):
        assert pr_tag_variants("49846") == ["pr=49846", "PR-49846"]

    def test_int_id(self):
        assert pr_tag_variants(49846) == ["pr=49846", "PR-49846"]

    def test_strips_new_format_prefix(self):
        assert pr_tag_variants("pr=49846") == ["pr=49846", "PR-49846"]

    def test_strips_legacy_prefix(self):
        assert pr_tag_variants("PR-49846") == ["pr=49846", "PR-49846"]

    def test_prefix_stripping_is_case_insensitive(self):
        """A user typing 'pr-49846' must not produce the malformed tag 'pr=pr-49846'."""
        assert pr_tag_variants("pr-49846") == ["pr=49846", "PR-49846"]
        assert pr_tag_variants("PR=49846") == ["pr=49846", "PR-49846"]

    def test_tolerates_surrounding_whitespace(self):
        assert pr_tag_variants("  49846 ") == ["pr=49846", "PR-49846"]

    def test_variants_match_the_parser(self):
        """Both spellings must be recognized by TAG_PR_RE — the producer/parser contract."""
        for tag in pr_tag_variants(49846):
            match = TAG_PR_RE.match(tag)
            assert match, tag
            assert match.group(1) == "49846"

    def test_new_format_variant_matches_format_pr_tag(self):
        assert pr_tag_variants(49846)[0] == format_pr_tag(49846)
