import re
from collections import deque
from typing import Any, Optional, Union

import pywikibot
from dateutil.parser import parse
from wikidata_bot_framework import (
    EntityPage,
    ExtraProperty,
    ExtraQualifier,
    ExtraReference,
    Output,
    OutputHelper,
    ProcessReason,
    PropertyAdderBot,
    get_random_hex,
    report_exception,
    session,
    site,
)

from .constants import *
from .inversedict import InverseDict


def load_package_info():
    query = "SELECT ?item ?npmName WHERE { ?item wdt:P8262 ?npmName. }"
    r = session.get(
        "https://query.wikidata.org/sparql",
        params={"query": query},
        headers={"Accept": "application/sparql-results+json;charset=utf-8"},
    )
    r.raise_for_status()
    return InverseDict(
        {
            item["npmName"]["value"]: item["item"]["value"].split("/")[-1]
            for item in r.json()["results"]["bindings"]
        }
    )


class NPMBot(PropertyAdderBot):
    def __init__(self):
        super().__init__()
        self.npm_db = load_package_info()
        self.queue: deque[str] = deque(self.npm_db.values())
        self.no_add_cache = set()
        self.editgroup_id = get_random_hex()

    def get_edit_group_id(self) -> Union[str, None]:
        return self.editgroup_id

    def get_edit_summary(self, page: EntityPage) -> str:
        if page.getID(True) == -1:
            base = "Creating item for missing NPM package."
        else:
            base = "Adding information from NPM."
        return f"{base} ([[User:RPI2026F1Bot/Task4|info]])"

    def get_reference(self, source_npm_package: str) -> ExtraReference:
        ref = ExtraReference(
            url_match_pattern=re.compile(
                npm_endpoint.format(package=source_npm_package).replace(".", r"\.")
            )
        )
        claim = pywikibot.Claim(site, stated_in_prop)
        claim.setTarget(pywikibot.ItemPage(site, npm_item))
        ref.add_claim(claim)
        url_claim = pywikibot.Claim(site, reference_url_prop)
        url_claim.setTarget(npm_endpoint.format(package=source_npm_package))
        ref.add_claim(url_claim)
        return ref

    def make_new_item(self, package: str) -> pywikibot.ItemPage:
        item = pywikibot.ItemPage(site)
        oh = OutputHelper()
        item.editLabels({"en": package}, summary=self._get_full_summary(item))
        claim = pywikibot.Claim(site, npm_package_prop)
        claim.setTarget(package)
        oh.add_property(ExtraProperty(claim))
        self.process(oh, item)
        return item

    def make_item_for_package(self, package: str) -> bool:
        if package in self.no_add_cache:
            return False
        r = session.get(npm_download_endpoint.format(package=package))
        r.raise_for_status()
        data = r.json()
        return data["downloads"] >= 100000

    def get_extra_property(self, package: str, claim: pywikibot.Claim) -> ExtraProperty:
        return ExtraProperty(claim, extra_references=[self.get_reference(package)])

    def processed_hook(
        self,
        item: EntityPage,
        reason: ProcessReason,
        *,
        claim: Optional[ExtraProperty] = None,
        qualifier: Optional[ExtraQualifier] = None,
        reference: Optional[ExtraReference] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        if reason.new_qualifier_was_added():
            assert claim is not None
            assert qualifier is not None
            if (
                qualifier.claim.getID() == version_type
                and claim.claim.getID() == software_version_identifier
            ):
                ref = pywikibot.Claim(site, based_on_heuristic)
                ref.setTarget(pywikibot.ItemPage(site, inferred_from_version))
                extra_ref = ExtraReference(retrieved=False)
                extra_ref.add_claim(ref, also_match_property_values=True)
                claim.add_reference(extra_ref)
        return False

    def run_item(
        self,
        item: EntityPage,
    ) -> Output:
        oh = OutputHelper()
        package_id = self.npm_db.get_key(item.getID())
        r = session.get(npm_endpoint.format(package=package_id))
        r.raise_for_status()
        data = r.json()
        current_version = data["dist-tags"]["latest"]
        if "repository" in data and False:  # We skip repo for now
            repo = data["repository"]
            if isinstance(repo, dict) and "url" in repo:
                repo = repo["url"]
            if valid_repo_url_regex.match(repo):
                claim = pywikibot.Claim(site, source_code_repo)
                claim.setTarget(repo)
                oh.add_property(self.get_extra_property(package_id, claim))
            elif match := valid_repo_git_url_regex.match(repo):
                claim = pywikibot.Claim(site, source_code_repo)
                claim.setTarget(match.group(1))
                oh.add_property(self.get_extra_property(package_id, claim))
            elif match := valid_repo_github_regex.match(repo):
                claim = pywikibot.Claim(site, source_code_repo)
                claim.setTarget(f"https://github.com/{match.group(1)}/{match.group(2)}")
                oh.add_property(self.get_extra_property(package_id, claim))
        deps = list(
            data["versions"][current_version].get("dependencies", {}).keys()
        ) + list(data["versions"][current_version].get("peerDependencies", {}).keys())
        for dep in deps:
            # Rudimentary check to see if the package is a type package.
            if dep.startswith("@types/") or ("/" in dep and "types" in dep.split("/")):
                continue
            if dep not in self.npm_db:
                if self.make_item_for_package(dep):
                    item = self.make_new_item(dep)
                    self.npm_db[dep] = item.getID()
                    self.queue.appendleft(item.getID())
                else:
                    self.no_add_cache.add(dep)
                    continue
            claim = pywikibot.Claim(site, dependency_prop)
            claim.setTarget(pywikibot.ItemPage(site, self.npm_db[dep]))
            oh.add_property(self.get_extra_property(package_id, claim))
        version_times = data["time"]
        del version_times["created"]
        del version_times["modified"]
        for version, created_at in version_times.items():
            claim = pywikibot.Claim(site, software_version_identifier)
            claim.setTarget(version)
            extra_property = self.get_extra_property(package_id, claim)
            qual = pywikibot.Claim(site, publication_date)
            try:
                timestamp = pywikibot.Timestamp.strptime(
                    created_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
            except ValueError:
                try:
                    timestamp = pywikibot.Timestamp.strptime(
                        created_at, "%Y-%m-%dT%H:%M:%SZ"
                    )
                except ValueError:
                    timestamp = parse(created_at)
            pub_time = pywikibot.WbTime.fromTimestamp(
                timestamp,
                precision=pywikibot.WbTime.PRECISION["day"],
            )
            qual.setTarget(pub_time)
            extra_property.add_qualifier(ExtraQualifier(qual))
            if "alpha" in version:
                qual = pywikibot.Claim(site, version_type)
                qual.setTarget(pywikibot.ItemPage(site, alpha))
                extra_property.add_qualifier(
                    ExtraQualifier(qual, skip_if_conflicting_exists=True)
                )
            elif "beta" in version or "next" in version:
                qual = pywikibot.Claim(site, version_type)
                qual.setTarget(pywikibot.ItemPage(site, beta))
                extra_property.add_qualifier(
                    ExtraQualifier(qual, skip_if_conflicting_exists=True)
                )
            elif "rc" in version:
                qual = pywikibot.Claim(site, version_type)
                qual.setTarget(pywikibot.ItemPage(site, rc))
                extra_property.add_qualifier(
                    ExtraQualifier(qual, skip_if_conflicting_exists=True)
                )
            elif "pre" in version:
                qual = pywikibot.Claim(site, version_type)
                qual.setTarget(pywikibot.ItemPage(site, pre))
                extra_property.add_qualifier(
                    ExtraQualifier(qual, skip_if_conflicting_exists=True)
                )
            elif (
                "dev" in version
                or "test" in version
                or "snapshot" in version
                or "nightly" in version
                or "canary" in version
            ):
                qual = pywikibot.Claim(site, version_type)
                qual.setTarget(pywikibot.ItemPage(site, unstable))
                extra_property.add_qualifier(
                    ExtraQualifier(qual, skip_if_conflicting_exists=True)
                )
            else:
                qual = pywikibot.Claim(site, version_type)
                qual.setTarget(pywikibot.ItemPage(site, stable))
                extra_property.add_qualifier(
                    ExtraQualifier(qual, skip_if_conflicting_exists=True)
                )
            qual = pywikibot.Claim(site, distributed_by)
            qual.setTarget(pywikibot.ItemPage(site, npmjs))
            extra_property.add_qualifier(ExtraQualifier(qual))
            qual = pywikibot.Claim(site, described_at_url)
            qual.setTarget(f"https://www.npmjs.com/package/{package_id}/v/{version}")
            extra_property.add_qualifier(ExtraQualifier(qual))
            version_data = data["versions"].get(version, {})
            if not version_data:
                continue
            dist_data = version_data.get("dist", {})
            qual = pywikibot.Claim(site, download_link)
            qual.setTarget(dist_data["tarball"])
            extra_property.add_qualifier(ExtraQualifier(qual))
            oh.add_property(extra_property)
            if "unpackedSize" in dist_data:
                qual = pywikibot.Claim(site, data_size)
                qual.setTarget(
                    pywikibot.WbQuantity(
                        dist_data["unpackedSize"],
                        pywikibot.ItemPage(site, byte),
                        site=site,
                    )
                )
                extra_property.add_qualifier(ExtraQualifier(qual))
        if len(oh.get(software_version_identifier, []) or []) > 300:
            oh[software_version_identifier].sort(
                key=lambda property: (
                    property.qualifiers[version_type][0].claim.getTarget().getID()
                    == stable,
                    property.qualifiers[publication_date][0]
                    .claim.getTarget()
                    .toTimestamp(),
                ),
                reverse=True,
            )
            oh[software_version_identifier] = oh[software_version_identifier][:300]

        claim = pywikibot.Claim(site, instance_of_prop)
        claim.setTarget(pywikibot.ItemPage(site, js_package))
        oh.add_property(ExtraProperty(claim))
        claim = pywikibot.Claim(site, programmed_in_prop)
        claim.setTarget(pywikibot.ItemPage(site, js))
        oh.add_property(ExtraProperty(claim, skip_if_conflicting_exists=True))
        claim = pywikibot.Claim(site, operating_system)
        claim.setTarget(pywikibot.ItemPage(site, cross_platform))
        oh.add_property(ExtraProperty(claim, skip_if_conflicting_exists=True))
        return oh

    def pre_edit_process_hook(self, output: Output, item: EntityPage) -> None:
        if software_version_identifier in item.claims:
            stable_version: pywikibot.Claim = sorted(
                item.claims[software_version_identifier],
                key=lambda property: (
                    property.qualifiers[version_type][0].getTarget().getID() == stable,
                    property.qualifiers[publication_date][0].getTarget().toTimestamp(),
                ),
                reverse=True,
            )[0]
            stable_version.rank = "preferred"
            for claim in item.claims[software_version_identifier]:
                if claim != stable_version:
                    claim.rank = "normal"
            item.claims[software_version_identifier].sort(
                key=lambda claim: claim.qualifiers[publication_date][0]
                .getTarget()
                .toTimestamp()
                if publication_date in claim.qualifiers
                else pywikibot.Timestamp.min
            )
        return super().pre_edit_process_hook(output, item)

    def run(self):
        while self.queue:
            item_id = self.queue.popleft()
            item = pywikibot.ItemPage(site, item_id)
            try:
                self.process(self.run_item(item), item)
            except Exception as e:
                report_exception(e)
            del item
