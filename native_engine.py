"""Subprocess bridge to the complete, isolated base-game rules engine."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading

ROOT = Path(__file__).resolve().parent

def executable():
    suffix = '.exe' if os.name == 'nt' else ''
    return ROOT / 'engine' / 'target' / 'release' / ('balatro-reader-engine' + suffix)

def request(payload, progress=None, cancelled=None):
    binary = executable()
    if not binary.is_file():
        return {'status':'blocked','reason':'Falta preparar el motor completo. Ejecutá Instalar.cmd para instalarlo.'}
    proc = subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,text=True,encoding='utf-8',
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    messages = queue.Queue()
    errors = []
    def read_output():
        try:
            for line in proc.stdout:
                messages.put(json.loads(line))
        except Exception as exc:
            messages.put({'status':'blocked','reason':'Respuesta inválida del motor: '+str(exc)})
        finally:
            messages.put(None)
    def read_errors():
        for line in proc.stderr:
            if len(errors)<30:
                errors.append(line.rstrip())
    out = threading.Thread(target=read_output,daemon=True)
    err = threading.Thread(target=read_errors,daemon=True)
    out.start();err.start()
    try:
        proc.stdin.write(json.dumps(payload,ensure_ascii=False)+'\n')
        proc.stdin.close()
        final = None
        while True:
            if cancelled and cancelled():
                proc.kill()
                return {'status':'superseded'}
            try:
                message = messages.get(timeout=.1)
            except queue.Empty:
                continue
            if message is None:
                break
            final = message
            if progress and message.get('status')=='running':
                progress(message.get('completed',0),message.get('total',0),message)
        proc.wait(timeout=5)
        if proc.returncode:
            return {'status':'blocked','reason':'El motor no pudo terminar: '+' '.join(errors)}
        return final or {'status':'blocked','reason':'El motor no devolvió resultados.'}
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
        out.join(timeout=1);err.join(timeout=1)
        proc.stdout.close();proc.stderr.close()

def analyze(state,trials=1000,seed=20261003,progress=None,cancelled=None,algorithm='exhaustive'):
    if algorithm not in ('exhaustive','genetic'):
        return {'status':'blocked','reason':'Algoritmo desconocido.'}
    r=state.get('round') or {}
    if state.get('state')!='SELECTING_HAND' or r.get('hands_left',0)<1:
        return {'status':'waiting','reason':'Esperando una mano disponible para jugar.'}
    if algorithm == 'genetic':
        catalog=request({'op':'catalog'},cancelled=cancelled)
        if catalog.get('status') == 'superseded': return catalog
        if algorithm not in catalog.get('search_modes',[]):
            return {'status':'blocked','reason':'Actualizá el motor con Instalar.cmd para usar la búsqueda genética.'}
    return request({'op':'analyze','state':state,'trials':trials,'seed':seed,'algorithm':algorithm},progress,cancelled)
