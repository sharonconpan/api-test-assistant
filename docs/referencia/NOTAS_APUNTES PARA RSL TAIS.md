## **2\. Cada compañera, la primera vez**

```
git clone https://github.com/mariaSolangeEzcurra/Prototipo-DeltaHeal.git
cd Prototipo-DeltaHeal
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

En `.env`, cada una pone **su propia clave de Gemini**, sacada de aistudio.google.com/apikey con su cuenta. Cada cuenta tiene su propia cuota, y como el modelo sigue siendo `gemini-3.8-flash`, los resultados son comparables.

Después, con Docker Desktop abierto, prepara las APIs (una sola vez por PC, porque la carpeta `benchmark/apis/` no se sube a GitHub):

```
python benchmark/setup_apis.py
```

## **3\. Para continuar el experimento (cualquiera de ustedes)**

```
git pull
python benchmark/run_benchmark.py
```

Cuando termine o se acabe la cuota, sube lo nuevo:

```
git add benchmark/results
git commit -m "Más corridas del experimento"
git push
```

## **Reglas importantes**

1. **Solo una persona ejecuta a la vez.** Si dos corren al mismo tiempo, ambas modifican `results.csv` y git dará conflictos al subir. Avísense por el grupo: "estoy corriendo yo" y "ya subí".  
2. **Siempre `git pull` antes de ejecutar** y `git push` al terminar.  
3. **Nadie cambia `benchmark.yaml`** ni el modelo durante el experimento.  
4. **Nadie borra la carpeta `benchmark\results`.**

