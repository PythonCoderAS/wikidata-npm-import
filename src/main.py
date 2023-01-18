from collections import deque
from typing import Union

import pywikibot

from wikidata_bot_framework import (
    ExtraProperty,
    ExtraReference,
    Output,
    OutputHelper,
    PropertyAdderBot,
    get_random_hex,
    EntityPage
)

from .constants import (
    cross_platform,
    dependency_prop,
    instance_of_prop,
    js,
    js_package,
    npm_download_endpoint,
    npm_endpoint,
    npm_item,
    npm_package_prop,
    operating_system,
    programmed_in_prop,
    reference_url_prop,
    session,
    site,
    stated_in_prop,
    valid_repo_git_url_regex,
    valid_repo_github_regex,
    valid_repo_url_regex,
    source_code_repo
)
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
        if page.getID() == -1:
            return "Creating item for missing NPM package."
        else:
            return "Adding dependency information."

    def get_reference(self, source_npm_package: str) -> ExtraReference:
        ref = ExtraReference(
            url_match_pattern=npm_endpoint.format(package=source_npm_package)
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
        item.labels = {"en": package}
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
        if "repository" in data:
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
                    continue
            claim = pywikibot.Claim(site, dependency_prop)
            claim.setTarget(pywikibot.ItemPage(site, self.npm_db[dep]))
            oh.add_property(self.get_extra_property(package_id, claim))

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

    def run(self):
        while self.queue:
            item_id = self.queue.pop()
            item = pywikibot.ItemPage(site, item_id)
            self.process(self.run_item(item), item)
