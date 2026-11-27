import sys; sys.path.insert(0,"/tmp/work")
src=open("/tmp/work/reg2.py").read().split("tr=sitk.Euler3DTransform()")[0]
exec(src)
def mk_tr(p):
    t=sitk.Euler3DTransform(); t.SetCenter(cf.tolist()); t.SetParameters(p); return t
base=list(sitk.Euler3DTransform().GetParameters()); 
t0=sitk.Euler3DTransform(); t0.SetCenter(cf.tolist()); t0.SetTranslation((cm-cf).tolist())
p0=np.array(t0.GetParameters()); print("init params",p0)
reg=sitk.ImageRegistrationMethod(); reg.SetMetricAsMattesMutualInformation(48)
reg.SetMetricSamplingStrategy(reg.RANDOM); reg.SetMetricSamplingPercentage(0.02,7)
reg.SetMetricMovingMask(mmask); reg.SetInterpolator(sitk.sitkLinear)
def metric(p):
    reg.SetInitialTransform(mk_tr(list(p)),inPlace=False); return reg.MetricEvaluate(fixed,mov)
print("init MI",metric(p0))
from scipy.optimize import minimize
# parameter scales: angles in rad (~ x 20mm radius), translations in mm
scale=np.array([0.02,0.02,0.02,1.0,1.0,1.0])
t=time.time()
best=p0.copy(); bv=metric(best)
for rnd in range(3):
    r=minimize(lambda q: metric(best+q*scale), np.zeros(6), method="Powell", options={"xtol":1e-2,"ftol":1e-4,"maxiter":4})
    best=best+r.x*scale; bv=r.fun; print("round",rnd,"MI",bv,"params",np.round(best,4),f"{time.time()-t:.0f}s",flush=True)
np.save("rigid_params.npy",best); np.save("rigid_center.npy",cf)
