import os
from matplotlib import pyplot as plt
from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit
from numpy import pi

dir = "circuit_drawings"
file_ending = ".pdf"
output = "mpl"
scale = 1
with_layout=False
plot_barriers=False
fold = 11

try:
    os.makedirs("circuit_drawings")
except FileExistsError:
    pass


def save_figure(circuit:QuantumCircuit, scale, fold, with_layout, plot_barriers, filename):
    circuit.draw(output="mpl", scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, style={"margin":[1.7,0,0,0], "figwidth":8},  filename=filename)

bv_qreg_q = QuantumRegister(2, 'q')
bv_creg_meas = ClassicalRegister(2, 'meas')
bv = QuantumCircuit(bv_qreg_q, bv_creg_meas)

bv.rz(1.5707963267948961, bv_qreg_q[0])
bv.sx(bv_qreg_q[0])
bv.rz(1.5707963267948966, bv_qreg_q[0])
bv.rz(1.5707963267948966, bv_qreg_q[1])
bv.sx(bv_qreg_q[1])
bv.rz(4.71238898038469, bv_qreg_q[1])
bv.cx(bv_qreg_q[0], bv_qreg_q[1])
bv.rz(1.5707963267948961, bv_qreg_q[0])
bv.sx(bv_qreg_q[0])
bv.rz(1.5707963267948966, bv_qreg_q[0])
bv.rz(1.5707963267948961, bv_qreg_q[1])
bv.sx(bv_qreg_q[1])
bv.rz(1.5707963267948966, bv_qreg_q[1])
bv.barrier(bv_qreg_q[0], bv_qreg_q[1])
bv.measure(bv_qreg_q[0], bv_creg_meas[0])
bv.measure(bv_qreg_q[1], bv_creg_meas[1])

bv.draw(output=output, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/bv{file_ending}") 

qft_qreg_q = QuantumRegister(2, 'q')
qft_creg_meas = ClassicalRegister(2, 'meas')
qft = QuantumCircuit(qft_qreg_q, qft_creg_meas)

qft.rz(1.5707963267948966, qft_qreg_q[0])
qft.sx(qft_qreg_q[0])
qft.rz(2.356194490192344, qft_qreg_q[0])
qft.cx(qft_qreg_q[0], qft_qreg_q[1])
qft.rz(5.497787143782137, qft_qreg_q[1])
qft.cx(qft_qreg_q[0], qft_qreg_q[1])
qft.rz(2.356194490192344, qft_qreg_q[1])
qft.sx(qft_qreg_q[1])
qft.rz(1.5707963267948966, qft_qreg_q[1])
qft.barrier(qft_qreg_q[0], qft_qreg_q[1])
qft.measure(qft_qreg_q[0], qft_creg_meas[0])
qft.measure(qft_qreg_q[1], qft_creg_meas[1])

qft.draw(output=output, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/qft{file_ending}") 

hwea_qreg_q = QuantumRegister(2, 'q')
hwea_creg_meas = ClassicalRegister(2, 'meas')
hwea = QuantumCircuit(hwea_qreg_q, hwea_creg_meas)

hwea.rz(4.71238898038469, hwea_qreg_q[0])
hwea.sx(hwea_qreg_q[0])
hwea.rz(1.5707963267948966, hwea_qreg_q[0])
hwea.cx(hwea_qreg_q[0], hwea_qreg_q[1])
hwea.sx(hwea_qreg_q[0])
hwea.sx(hwea_qreg_q[0])
hwea.rz(3.141592653589793, hwea_qreg_q[0])
hwea.barrier(hwea_qreg_q[0], hwea_qreg_q[1])
hwea.measure(hwea_qreg_q[0], hwea_creg_meas[0])
hwea.measure(hwea_qreg_q[1], hwea_creg_meas[1])

hwea.draw(output=output, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/hwea{file_ending}") 

uccsd_qreg_q = QuantumRegister(2, 'q')
uccsd_creg_meas = ClassicalRegister(2, 'meas')
uccsd = QuantumCircuit(uccsd_qreg_q, uccsd_creg_meas)

uccsd.rz(1.5707963267948961, uccsd_qreg_q[0])
uccsd.sx(uccsd_qreg_q[0])
uccsd.rz(1.5707963267948966, uccsd_qreg_q[0])
uccsd.rz(1.5707963267948961, uccsd_qreg_q[1])
uccsd.sx(uccsd_qreg_q[1])
uccsd.rz(1.5707963267948966, uccsd_qreg_q[1])
uccsd.cx(uccsd_qreg_q[1], uccsd_qreg_q[0])
uccsd.rz(-1.4877468618698795, uccsd_qreg_q[0])
uccsd.cx(uccsd_qreg_q[1], uccsd_qreg_q[0])
uccsd.sx(uccsd_qreg_q[0])
uccsd.rz(1.5707963267948948, uccsd_qreg_q[0])
uccsd.sx(uccsd_qreg_q[1])
uccsd.rz(1.5707963267948948, uccsd_qreg_q[1])
uccsd.cx(uccsd_qreg_q[1], uccsd_qreg_q[0])
uccsd.rz(-1.4877468618698795, uccsd_qreg_q[0])
uccsd.cx(uccsd_qreg_q[1], uccsd_qreg_q[0])
uccsd.rz(3.141592653589793, uccsd_qreg_q[0])
uccsd.sx(uccsd_qreg_q[0])
uccsd.rz(3.141592653589793, uccsd_qreg_q[0])
uccsd.rz(3.141592653589793, uccsd_qreg_q[1])
uccsd.sx(uccsd_qreg_q[1])
uccsd.rz(3.141592653589793, uccsd_qreg_q[1])
uccsd.barrier(uccsd_qreg_q[0], uccsd_qreg_q[1])
uccsd.measure(uccsd_qreg_q[0], uccsd_creg_meas[0])
uccsd.measure(uccsd_qreg_q[1], uccsd_creg_meas[1])

uccsd.draw(output=output, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/uccsd{file_ending}") 

from qiskit import QuantumRegister, ClassicalRegister, QuantumCircuit
from numpy import pi

aqft_qreg_q = QuantumRegister(2, 'q')
aqft_creg_meas = ClassicalRegister(2, 'meas')
aqft = QuantumCircuit(aqft_qreg_q, aqft_creg_meas)

aqft.rz(1.5707963267948966, aqft_qreg_q[0])
aqft.sx(aqft_qreg_q[0])
aqft.rz(2.356194490192344, aqft_qreg_q[0])
aqft.cx(aqft_qreg_q[0], aqft_qreg_q[1])
aqft.rz(5.497787143782137, aqft_qreg_q[1])
aqft.cx(aqft_qreg_q[0], aqft_qreg_q[1])
aqft.rz(2.356194490192344, aqft_qreg_q[1])
aqft.sx(aqft_qreg_q[1])
aqft.rz(1.5707963267948966, aqft_qreg_q[1])
aqft.barrier(aqft_qreg_q[0], aqft_qreg_q[1])
aqft.measure(aqft_qreg_q[0], aqft_creg_meas[0])
aqft.measure(aqft_qreg_q[1], aqft_creg_meas[1])

aqft.draw(output=output, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/aqft{file_ending}") 

sl_qreg_q = QuantumRegister(2, 'q')
sl_creg_meas = ClassicalRegister(2, 'meas')
supremacy_linear = QuantumCircuit(sl_qreg_q, sl_creg_meas)

supremacy_linear.rz(1.5707963267948961, sl_qreg_q[0])
supremacy_linear.sx(sl_qreg_q[0])
supremacy_linear.rz(1.5707963267948966, sl_qreg_q[0])
supremacy_linear.cx(sl_qreg_q[0], sl_qreg_q[1])
supremacy_linear.rz(3.1415926535897936, sl_qreg_q[0])
supremacy_linear.sx(sl_qreg_q[0])
supremacy_linear.rz(3.9269908169872423, sl_qreg_q[0])
supremacy_linear.sx(sl_qreg_q[0])
supremacy_linear.rz(4.71238898038469, sl_qreg_q[0])
supremacy_linear.rz(3.1415926535897936, sl_qreg_q[1])
supremacy_linear.sx(sl_qreg_q[1])
supremacy_linear.rz(3.9269908169872405, sl_qreg_q[1])
supremacy_linear.sx(sl_qreg_q[1])
supremacy_linear.rz(1.5707963267948943, sl_qreg_q[1])
supremacy_linear.barrier(sl_qreg_q[0], sl_qreg_q[1])
supremacy_linear.measure(sl_qreg_q[0], sl_creg_meas[0])
supremacy_linear.measure(sl_qreg_q[1], sl_creg_meas[1])

save_figure(circuit=bv, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/bv{file_ending}") 
save_figure(circuit=qft, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/qft{file_ending}") 
save_figure(circuit=hwea, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/hwea{file_ending}") 
save_figure(circuit=aqft, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/aqft{file_ending}") 
save_figure(circuit=uccsd, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/uccsd{file_ending}") 
save_figure(circuit=supremacy_linear, scale=scale, fold = fold, with_layout=with_layout, plot_barriers=plot_barriers, filename=f"{dir}/supremacy_linear{file_ending}") 

