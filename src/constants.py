import re

npm_endpoint = "https://registry.npmjs.com/{package}"
npm_download_endpoint = "https://api.npmjs.org/downloads/point/last-week/{package}"
valid_repo_github_regex = re.compile(r"^([a-zA-Z\d\-\._]+)/([a-zA-Z\d\-\._]+)$")
valid_repo_url_regex = re.compile(r"^https?://")
valid_repo_git_url_regex = re.compile(r"^git\+(https.+)\.git$")
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
source_code_repo = "P1324"
software_version_identifier = "P348"
publication_date = "P577"
version_type = "P548"
alpha = "Q2122918"
beta = "Q3295609"
rc = "Q1072356"
pre = "Q51930650"
unstable = "Q21727724"
stable = "Q2804309"
based_on_heuristic = "P887"
inferred_from_version = "Q116679778"
download_link = "P4945"
data_size = "P3575"
byte = "Q8799"
described_at_url = "P973"
distributed_by = "P750"
npmjs = "Q116058944"
most_recent_version = "Q71533355"