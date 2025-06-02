from bs4 import BeautifulSoup
import requests
from enum import Enum
import yagooglesearch
import re
import logging
from datetime import datetime
import os, json
import replicate
from dotenv import load_dotenv
load_dotenv() 


class JobSite(Enum):
    LEVER = "lever.co"
    GREENHOUSE = "boards.greenhouse.io/*/jobs/*"
    ASHBY = "ashbyhq.com"


class TBS(Enum):
    PAST_TWELVE_HOURS = "qdr:h12"
    PAST_DAY = "qdr:d"
    PAST_WEEK = "qdr:w"
    PAST_MONTH = "qdr:m"
    PAST_YEAR = "qdr:y"
    
def get_free_proxies() -> list[str]:
    url = "https://free-proxy-list.net/"
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find(
            "table", attrs={"class": "table table-striped table-bordered"}
        )
        rows = table.find_all("tr")
        proxies = []
        for row in rows:
            cols = row.find_all("td")
            if len(cols) > 0:
                ip = cols[0].text
                port = cols[1].text
                proxy = f"{ip}:{port}"
                proxies.append(proxy)
        return proxies
    except Exception as e:
        print("Error: ", e)
        return []

def extract_requirements(description: str) -> tuple[list[str], list[str]]:
        prompt = (
            "Extract the minimum years of experience required and the list of technical skills"
            "from the following job description. If not mentioned, guess the years of experience based on the job title. (0 years if nothing is mentioned)\n\n"
            "Respond *only* with a JSON object containing exactly two keys: "
            "`years` (an integer) and `skills` (an array of strings, less than 3 words).\n\n"
            f"Job Description:\n{description}"
        )

        # 4) Prepare the model input
        input_payload = {
            "prompt": prompt,
        }

        # 5) Call Replicate
        raw_output = replicate.run(
            "meta/meta-llama-3-8b-instruct",
            input=input_payload,
            temperature= 0.0,           # deterministic decoding
            stop= ["\n\n", "###"], 
        )

        # 6) Parse the JSON
        response_text = "".join(raw_output).strip()
        def extract_json_via_regex(text: str) -> dict:
            m = re.search(r'\{[\s\S]*?\}', text)
            if not m:
                raise ValueError("No JSON found")
            return json.loads(m.group())

        data = extract_json_via_regex(response_text)
        return data.get("years", 0), data.get("skills", ["None"])
    
def find_jobs(
    keyword: str,
    job_sites: list[JobSite],
    tbs: TBS | None,
    max_results: int = 100,
):
    proxies = [None] + get_free_proxies()
    proxy_index = 0
    success = False
    result = []

    while not success:
        try:
            proxy = proxies[proxy_index]
            proxy_index += 1
            
            if proxy_index >= len(proxies):
                print("No more proxies to try.")
                break
            search_sites = " OR ".join([f"site:{site.value}" for site in job_sites])
            search_query = f"{keyword} {search_sites}"
            
            client = yagooglesearch.SearchClient(
                search_query,
                tbs=tbs.value if tbs else None,
                max_search_result_urls_to_return=max_results,
                proxy=proxy,
                verbosity=0,
            )
            client.assign_random_user_agent()
            result = client.search()
            print(f"Found {len(result)} results")
            success = True
        except Exception as e:
            print(f"Error using proxy {proxy}: ", e)

    job_urls_by_board = {}
    for job_site in job_sites:
        job_urls_for_job_site = [
            url for url in result if re.search(regex[job_site], url)
        ]
        cleaner = JobSearchResultCleaner(job_site)
        job_urls_by_board[job_site] = cleaner.clean(job_urls_for_job_site)
        
    return job_urls_by_board


def get_lever_job_details(link: str) -> list[str]:
    description_link = requests.get(link[:-6])
    soup_des = BeautifulSoup(description_link.content, "html.parser")
    description = soup_des.find("div", class_="section-wrapper page-full-width").get_text()
    ld_json = soup_des.find("script", {"type": "application/ld+json"}).string
    data = json.loads(ld_json)
    date = data.get("datePosted")
    unique_id = f"{link}_{date}"
    
    response = requests.get(link)
    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.title.string if soup.title else "Unknown"
    company_name = title.split("-")[0].strip() if "-" in title else title.strip()
    position = "-".join(title.split("-")[1:]).strip() if "-" in title else "Unknown"
    location = soup.find("div", class_="sort-by-time posting-category medium-category-label width-full capitalize-labels location").get_text(strip=True) if soup.find("div", class_="sort-by-time posting-category medium-category-label width-full capitalize-labels location") else "Unknown"
    img = soup.find("img")
    if img and img["src"] and img["src"] != "/img/lever-logo-full.svg":
        img_url = img["src"]
    else:
        img_url = None

    return [company_name, position, img_url, description, location, unique_id]


def get_greenhouse_job_details(link: str) -> list[str]:
    response = requests.get(link)
    soup = BeautifulSoup(response.content, "html.parser")
    
    render_date_str = soup.find("input", {"id": "render_date"})["value"]
    last_update = datetime.strptime(render_date_str, "%Y-%m-%d %H:%M:%S %z")
    unique_id = f"{link}"
    
    location = soup.find('div', class_='location').get_text(strip=True) if soup.find('div', class_='location') else "Unknown"
    
    descriptions = [block.get_text(separator='\n', strip=True) for block in soup.find_all('div', id='content')]if soup.find_all('div', id='content') else "Unknown"
    description = "\n".join(descriptions) if isinstance(descriptions, list) else "Unknown"
    
    head = soup.find("head")

    position = (
        head.find("meta", property="og:title")["content"]
        if head.find("meta", property="og:title")
        else "Unknown"
    )

    image = (
        head.find("meta", property="og:image")["content"]
        if head.find("meta", property="og:image")
        else None
    )

    title = soup.title.string if soup.title else "Unknown"

    company_name = title.split(" at ")[1].strip() if " at " in title else title.strip()
    return [company_name, position, image, description, location, unique_id] 


def get_ashby_job_details(link: str) -> list[str]:
    description_link = requests.get(link.replace("/application?", "?"))
    des_soup = BeautifulSoup(description_link.content, "html.parser")
    description_meta = des_soup.find('meta', attrs={'name': 'description'})
    description = description_meta['content'] if description_meta else "Unknown"

    text = str(des_soup)
    m = re.search(r'"locationName"\s*:\s*"([^"]+)"', text)
    location = m.group(1) if m else "Unknown"

    script = des_soup.find('script', string=lambda t: t and 'window.__appData' in t)
    text = script.string if script else ''
    m    = re.search(r'"updatedAt"\s*:\s*"([^"]+)"', text)
    updated_at = m.group(1) if m else 0
    dt = datetime.fromisoformat(updated_at.rstrip('Z'))
    date_update = dt.date().isoformat()    
    unique_id = f"{link}_{date_update}"
        
    response = requests.get(link)
    
    soup = BeautifulSoup(response.content, "html.parser")
    head = soup.find("head")
    title = head.find("title").string

    company_name = title.split(" @ ")[1].strip() if " @ " in title else title.strip()
    position = title.split(" @ ")[0].strip() if " @ " in title else "Unknown"

    image = (
        head.find("meta", property="og:image")["content"]
        if head.find("meta", property="og:title")
        else None
    )

    return [company_name, position, image, description, location, unique_id]
    
    

def handle_job_insert(supabase: any, job_urls: list[str], job_site: JobSite):
    for link in job_urls:
        try:
            # 1) scrape the details (incl. description)
            if job_site == JobSite.LEVER:
                company, title, img, description, location, unique_id = get_lever_job_details(link)
            elif job_site == JobSite.GREENHOUSE:
                company, title, img, description, location, unique_id = get_greenhouse_job_details(link)
            else:
                company, title, img, description, location, unique_id = get_ashby_job_details(link)

            # 2) extract years & skills from that description
            existing_resp = (
                supabase
                .from_("jobs")
                .select("unique_id")   
                .eq("unique_id", unique_id)
                .execute()
            )
        
            # If row_count > 0, that unique_id is already present → skip
            if len(existing_resp.data) > 0:
                logging.info("Skipping %s (already exists)", unique_id)
                continue
            
            
            years, skills = 0, ["None"]
            years, skills = extract_requirements(description)
            
            # 3) build your record
            record = {
                "unique_id": unique_id,
                "company":   company,
                "job_title": title,
                "image":     img,
                "description": description,
                "location":  location,
                "years":     years,
                "skills":    skills,
                "job_url":   link,
                "job_board": job_site.name,
            }

            # 4) insert or upsert into your DB
            
            response = (
                    supabase
                    .from_("jobs")
                    .upsert(record, on_conflict="unique_id")
                    .execute()
                )

            logging.info("Upsert succeeded for %s", unique_id)


        except Exception as e:
            logging.error("Failed to process %s: %s", link, e)
            
            

regex = {
    JobSite.LEVER: r"https://jobs.lever.co/[^/]+/[^/]+",
    JobSite.GREENHOUSE: r"https://boards.greenhouse.io/[^/]+/jobs/[^/]+",
    JobSite.ASHBY: r"https://jobs.ashbyhq.com/[^/]+/[^/]+",
}


class JobSearchResultCleaner:

    def __init__(self, job_site: JobSite):
        self.job_site = job_site

    def _prune_urls(self, urls: list[str]) -> list[str]:
        return [
            re.search(regex[self.job_site], url).group()
            for url in urls
            if re.search(regex[self.job_site], url)
        ]

    def _remove_duplicates(self, urls: list[str]) -> list[str]:
        return list(set(urls))

    def _make_direct_apply_urls(self, urls: list[str]) -> list[str]:
        if self.job_site == JobSite.LEVER:
            urls = [re.sub(r"\?.*", "", url) for url in urls]

            return [url + "/apply" for url in urls]
        if self.job_site == JobSite.GREENHOUSE:
            cleaned_urls = [re.sub(r"\?.*", "", url) for url in urls]
            urls = [
                re.sub(
                    r"https://boards.greenhouse.io/([^/]+)/jobs/([^/]+)",
                    r"https://boards.greenhouse.io/embed/job_app?for=\1&token=\2",
                    url,
                )
                for url in cleaned_urls
            ]
            return urls
        if self.job_site == JobSite.ASHBY:
            urls = [re.sub(r"\?.*", "", url) for url in urls]
            return [url + "/application?embed=js" for url in urls]
        
        return urls

    def clean(self, job_search_result: list) -> list[str]:
        """Clean the job search result to only include valid job URLs."""
        if not job_search_result:
            return []
        try:
            return self._make_direct_apply_urls(
                self._remove_duplicates(self._prune_urls(job_search_result))
            )
        except Exception as e:
            print(f"Error cleaning job search result: {e}")
            return []
        
        
if __name__ == "__main__":
    main()