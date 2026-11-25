"""Official national aggregates from STAR, Statistics Denmark and Eurostat."""
import csv
import io
import json
import math
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

STAR = "https://jobindsats.dk/Metadata/"
DST = "https://api.statbank.dk/v1/"

def request(url, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"User-Agent": "Arbejdsmarkedet-lige-nu/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    for attempt in range(3):
        try:
            with urlopen(Request(url, data=body, headers=headers), timeout=65) as response:
                return response.read().decode("utf-8-sig")
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))

def number(value):
    if value is None or str(value).strip() in ("", ".", "..", "-", ":", "M"):
        return None
    value = float(str(value).strip().replace(",", "."))
    if not math.isfinite(value):
        raise ValueError("Ugyldigt tal")
    return value

def monthly(table, measures, *, dimensions=None, months=121):
    metadata = json.loads(request(STAR + "DatabankElementPage?" + urlencode({"maalingId":table})))
    periods = sorted({p["period"].strip() for p in metadata["periodes"] if p["periodType"].strip() == "M"})[-months:]
    area = next(h["hierarchyId"] for h in metadata["maalingHierarchiesContainer"] if h["dimensionId"] == "_omrade" and h["hierarchyId"] in ("_nykom","_hele_landet"))
    selected = dimensions or {}
    payload = {
        "cube":table, "period":json.dumps({"period":periods}),
        "area":json.dumps({area:["Hele landet"]}), "measure":json.dumps({"measure":measures}),
        "dimension":json.dumps({"dimension":list(selected)}) if selected else None,
    }
    for i,(dimension, members) in enumerate(selected.items(),1):
        payload["dim"+str(i)] = json.dumps({dimension:members})
    data = json.loads(request(STAR+"getdata", payload))
    columns = data["header"][0]
    codes = {g["mgroup_id"]:g["measure"][0]["meas_memb_id"] for g in data["header"][3]["mgroup"]}
    rows = []
    for row in data["data"]:
        values = {dim:row[columns.index(dim + "_txt")] for dim in selected}
        values["period"] = row[columns.index("periode")].strip()
        values["values"] = [number(row[columns.index(codes[m])]) for m in measures]
        if values["period"] not in periods:
            raise ValueError("Uventet periode")
        rows.append(values)
    if not rows: raise ValueError("Tom STAR-besvarelse: "+table)
    return rows

def as_series(rows):
    result = {r["period"]:r["values"] for r in rows}
    if len(result) != len(rows): raise ValueError("Flere observationer for samme måned")
    return result

def star_simple(table, *measures):
    return as_series(monthly(table,list(measures)))

def longterm():
    members = ["Ydelsesgrupper i alt","A-dagpenge"]
    rows = monthly("y25i09", ["mgrpy25i09_4"], dimensions={"_ygrpi09":members})
    total, insured = [as_series([r for r in rows if r["_ygrpi09"] == name]) for name in members]
    if not total or total.keys() != insured.keys():
        raise ValueError("Langtidsledighed mangler en ydelsesgruppe")
    return {p:[total[p][0], insured[p][0]] for p in total}

def foreigners():
    rows = monthly("y24b", ["mgrpy24b_1","mgrpy24b_2"])
    return as_series(rows)

def foreign_share(workers):
    total = star_simple("y25l01","mgrpy25l01_2")
    return {p:[100*workers[p][1]/total[p][0]] for p in workers.keys() & total.keys()
            if workers[p][1] is not None and total[p][0] and total[p][0]>0}

def seniors():
    age = [str(i)+" år" for i in range(55,75)]+["75+ år"]
    states = ["Status i alt","Lønmodtagerbeskæftigelse i alt","Tilbagetræknings- og øvrig off. ydelse i alt","Egen pension og selvforsørgelse i alt"]
    rows = monthly("snr_arbstatus",["mgrpsnr_arbstatus_ap"],dimensions={"_snr_arbstatus":states,"_alder_snr":age},months=1)
    counts={(r["_alder_snr"],r["_snr_arbstatus"]):r["values"][0] for r in rows}
    result=[]
    for a in age:
        total=counts[a,states[0]]
        parts=[counts.get((a,s)) for s in states[1:]]
        if total and None not in parts:
            if abs(sum(parts)-total)>2: raise ValueError("Seniorstatus summer ikke til befolkningen")
            parts=[100*v/total for v in parts]
        else: parts=[None]*3
        result.append([a,*parts])
    return rows[0]["period"], result

def statbank(table, selection, month_limit=121):
    meta=json.loads(request(DST+"tableinfo/"+table+"?format=JSON&lang=da"))
    dates=sorted(v["id"] for v in next(d for d in meta["variables"] if d["time"])["values"])[-month_limit:]
    query={k:",".join(codes) for k,codes in selection.items()}
    query.update(Tid=",".join(dates),lang="da")
    csv_text=request(DST+"data/"+table+"/CSV?"+urlencode(query))
    rows=list(csv.DictReader(io.StringIO(csv_text),delimiter=";"))
    if not rows or "INDHOLD" not in rows[0]: raise ValueError("Uventet tabel: "+table)
    return [(r,number(r["INDHOLD"])) for r in rows]

def jobs():
    return {r["TID"]:[v] for r,v in statbank("LBESK104",{"SEKTOR":["1000"]})}

def prices():
    data={}
    for r,v in statbank("PRIS01",{"VAREGR":["000000","151"],"ENHED":["300"]}):
        col=int(r["VAREGR"].startswith("15.1") or "kerneinflation" in r["VAREGR"].lower())
        data.setdefault(r["TID"],[None,None])[col]=v
    return data

def age_rates():
    groups=["U25","O25","O30","O40","O50","O60"]
    rows=statbank("AUS07",{"YD":groups,"SAESONFAK":["9","10"]},1)
    data={}
    for r,v in rows:
        group=r["YD"]
        col=0 if "pct." in r["SAESONFAK"] else 1
        data.setdefault(group,[None,None])[col]=v
    if len(data)!=6 or any(None in v for v in data.values()): raise ValueError("Ufuldstændig aldersfordeling")
    return rows[0][0]["TID"],[[k,*v] for k,v in sorted(data.items())]

def branches():
    items=list("ABCDEFGHIJKLMNOPQRS")+["TUV"]
    data={}
    for r,v in statbank("LBESK103",{"BRANCHE1020":items},13):
        label=r["BRANCHE1020"].split(" ",1)[1]
        data.setdefault(r["TID"],{})[label]=v
    p=max(data); prior=data[str(int(p[:4])-1)+p[4:]]
    diffs=[[k,v-prior[k],100*(v/prior[k]-1)] for k,v in data[p].items() if v is not None and prior.get(k)]
    if len(diffs)!=len(items): raise ValueError("Branchetal mangler")
    diffs.sort(key=lambda r:-r[1])
    return p,[r for r in diffs if r[1]>0][:3]+[r for r in diffs if r[1]<0][-3:]

def international():
    names={"DK":"Danmark","FI":"Finland","SE":"Sverige","NO":"Norge","DE":"Tyskland","EU27_2020":"EU"}
    query=[("geo",k) for k in names]+[("s_adj","SA"),("s_adj","TC")]+list(dict(age="TOTAL",sex="T",unit="PC_ACT",lastTimePeriod=12,lang="en").items())
    d=json.loads(request("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m?"+urlencode(query)))
    periods=d["dimension"]["time"]["category"]["index"]
    for p in sorted(periods,reverse=True):
        values=[]
        for code,name in names.items():
            idx=0
            for dim,size in zip(d["id"],d["size"]):
                selection = {"geo":code, "time":p, "s_adj":"SA" if code in ("DK","EU27_2020") else "TC"}
                pos=d["dimension"][dim]["category"]["index"][selection[dim]] if dim in selection else 0
                if dim not in selection and size!=1:raise ValueError("Flere Eurostat-serier end forventet")
                idx=idx*size+pos
            value=d["value"].get(str(idx))
            if value is not None: values.append([name,value])
        if len(values)==len(names): return p.replace("-","M"),sorted(values,key=lambda r:-r[1])
    raise ValueError("Ingen fælles måned hos Eurostat")
