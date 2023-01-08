from requests import Session
from wikidata_bot_framework import site

session = Session()
npm_endpoint = "https://registry.npmjs.com/{package}"
npm_download_endpoint = "https://api.npmjs.org/downloads/point/last-week/{package}"
if site.code == "wikidata":
    npm_package_prop = "P8262"
    npm_item = "Q116058944"
    stated_in_prop = "P248"
    reference_url_prop = "P854"
    dependency_prop = "P1547"
    instance_of_prop = "P31"
    js_package = "Q783866"
    programmed_in_prop = "P277"
    js = "Q2005"
    operating_system = "P306"
    cross_platform = "Q174666"
else:
    import wikidata_bot_framework.dataclasses

    wikidata_bot_framework.dataclasses.site = site
    wikidata_bot_framework.dataclasses.retrieved_prop = "P97263"
    npm_package_prop = "P97255"
    npm_item = "Q227502"
    stated_in_prop = "P97256"
    reference_url_prop = "P97262"
    dependency_prop = "P97258"
    instance_of_prop = "P97259"
    js_package = "Q227503"
    programmed_in_prop = "P97260"
    js = "Q227504"
    operating_system = "P97261"
    cross_platform = "Q227506"
