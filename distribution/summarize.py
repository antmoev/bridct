"""Summarize completed sessions; retain incomplete runs without ranking them."""
from pathlib import Path
import argparse
import collections
import csv
import json
import math
import statistics


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--results',type=Path,required=True)
    args=parser.parse_args();root=args.results.resolve()
    status=(root/'status.txt').read_text() if (root/'status.txt').is_file() else 'Run status unavailable.'
    sections=[];contrasts=[];failures=[]
    for path in sorted(root.rglob('manifest.json')):
        if any(p in ('build','__pycache__') for p in path.relative_to(root).parts):continue
        meta=json.loads(path.read_text());name=path.parent.relative_to(root).as_posix()
        if meta.get('status') in ('VALIDATED','PASS'):continue
        if meta.get('status')!='COMPLETE_EXPLORATORY':
            failures.append({'session':name,'status':meta.get('status'),'error':meta.get('error')});continue
        timing=path.parent/'timing.csv'
        if not timing.is_file():failures.append({'session':name,'status':'MISSING_TIMING'});continue
        rows=list(csv.DictReader(timing.open()))
        grouped=collections.defaultdict(lambda: collections.defaultdict(dict))
        try:
            for row in rows:
                shape=(row.get('h',row.get('n')),row.get('w',row.get('n')))
                key=(*shape,row['b'],row.get('contract','native_c'),row['mode'])
                block=int(row['block']);arm=row['arm'];value=float(row['ns_array'])
                assert block not in grouped[key][arm] and math.isfinite(value) and value>0
                grouped[key][arm][block]=value
            blocks=set(range(meta['blocks']))
            assert rows and all(set(v)==blocks for arms in grouped.values() for v in arms.values())
            assert len(rows)==meta['rows']
        except (KeyError,ValueError,AssertionError) as error:
            failures.append({'session':name,'status':'INVALID_OR_INCOMPLETE_KEYS','error':repr(error)});continue
        session_rows=[]
        for key,arms in sorted(grouped.items()):
            candidate='selected_api' if 'selected_api' in arms else 'bridct'
            if candidate not in arms:continue
            x=statistics.median(arms[candidate].values())
            references=[arm for arm in arms if arm.startswith('ooura_')] if candidate=='selected_api' else [arm for arm in arms if arm!='bridct']
            for reference in sorted(references):
                y=statistics.median(arms[reference].values())
                session_rows.append(dict(session=name,h=key[0],w=key[1],b=key[2],contract=key[3],mode=key[4],candidate=candidate,reference=reference,bridct_us_per_array=x/1000,reference_us_per_array=y/1000,reference_over_bridct=y/x))
        contrasts.extend(session_rows)
        for reference in sorted({r['reference'] for r in session_rows}):
            selected=[r for r in session_rows if r['reference']==reference]
            sections.append(dict(session=name,reference=reference,cases=len(selected),favorable_medians=sum(r['reference_over_bridct']>1 for r in selected),ratio_min=min(r['reference_over_bridct'] for r in selected),ratio_max=max(r['reference_over_bridct'] for r in selected)))
    result={'run_status':status,'completed_comparisons':sections,'incomplete_or_invalid_sessions':failures,
            'interpretation':'Within-session ratios of observed medians; descriptive exploratory results, not statistical proof. Python APIs and native C are separate contracts. Ratio >1 favors BRiDCT. No overhead subtraction.'}
    corpus=root/'numerical-corpus/result.json'
    if corpus.is_file():result['numerical_validation']=json.loads(corpus.read_text())
    (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    if contrasts:
        with (root/'comparisons-all.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=contrasts[0],lineterminator='\n');writer.writeheader();writer.writerows(contrasts)
    text=['# Résultats BRiDCT sur cette machine','', '## État du lancement','', '```text',status.strip(),'```','']
    if 'numerical_validation' in result:
        c=result['numerical_validation']
        text += [f"Vérification numérique : **{c['status']}**, {c['shape_checks']+c['corpus_core_checks']} contrôles requis, {c['required_failures']} échec requis. Erreur maximale : {c['max_required_error']:.3g}. Les {c['boundary_failures']} échecs sur {c['boundary_checks']} diagnostics de frontière restent conservés ; ce ne sont pas des réussites numériques.",'']
    text += ['## Mesures terminées','', 'Un facteur **supérieur à 1** signifie que BRiDCT prend moins de temps. Les facteurs sont des rapports de médianes par cas ; la plage n’est ni une moyenne ni un intervalle de confiance. Les temps complets sont en **microsecondes par image** dans `comparisons-all.csv`. Les colonnes par session restent distinctes.','', '| Session | Référence | Cas | Médianes favorables à BRiDCT | Facteur min–max |','|---|---|---:|---:|---:|']
    for s in sections:
        text.append(f"| {s['session']} | {s['reference']} | {s['cases']} | {s['favorable_medians']} | {s['ratio_min']:.3f}–{s['ratio_max']:.3f} |")
    if not sections:text.append('| Aucune session complète vérifiée | — | — | — | — |')
    text += ['', 'Les sessions `opencv` et `libraries` incluent les appels Python et les allocations déclarées. Les sessions `ooura` sont des boucles C avec buffers préalloués. Ne pas mélanger ces catégories dans un classement. `ooura_public_f1` vient du code public Ooura converti mécaniquement en float32 ; `ooura_scalar/auto/neon/trusted` sont les adaptations attribuées de l’étude. Le comparateur `trusted` omet ses vérifications de préconditions.','', 'Les plans explicites FFTW sont préparés avant les mesures. Les créations éventuelles de plans dans l’interface FFTW à cache sont comptées par le banc ; leur coût est conservé. Les médianes d’un criblage court ne suffisent pas à établir une supériorité générale. CPU, compilateur, versions et charge peuvent changer les résultats.','']
    if failures:text += ['## Sessions incomplètes conservées','',*['- '+str(f) for f in failures],'']
    text += ['Les journaux et données brutes restent dans les sous-dossiers. Lire `host.txt`, `pip-freeze.txt`, les manifestes et `status.txt` pour interpréter une exécution. L’archive complète peut être renvoyée telle quelle.','']
    (root/'SUMMARY.fr.md').write_text('\n'.join(text))
    print(json.dumps({'status':'SUMMARY_WRITTEN','completed_groups':len(sections),'contrasts':len(contrasts),'incomplete_sessions':len(failures)}))


if __name__=='__main__':main()
