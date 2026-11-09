"""EMA teacher update and paired weak/strong views for unlabeled RGB tiles."""
from __future__ import annotations

import torch


def ema_update(teacher: torch.nn.Module, student: torch.nn.Module, decay: float) -> None:
    """In-place EMA of model weights; copy integer buffers exactly."""
    if not 0 < decay < 1:
        raise ValueError("EMA decay must be in (0,1)")
    teacher_state = teacher.state_dict()
    student_state = student.state_dict()
    if teacher_state.keys() != student_state.keys():
        raise ValueError("Teacher/student parameter structure differs")
    with torch.no_grad():
        for name, value in teacher_state.items():
            other = student_state[name]
            if value.shape != other.shape:
                raise ValueError(f"Teacher/student tensor shape differs: {name}")
            if value.is_floating_point():
                value.mul_(decay).add_(other, alpha=1 - decay)
            else:
                value.copy_(other)


def paired_weak_strong(pre: torch.Tensor, post: torch.Tensor, pseudo: torch.Tensor,
                       brightness: float, contrast: float):
    """Apply one spatial transform to PRE/POST/pseudo, then stronger shared RGB jitter.

    All tensors are B×C×H×W. The pseudo mask uses values 0/1/255 and receives
    spatial transforms only; strong jitter is identical for PRE and POST.
    """
    if pre.ndim != 4 or pre.shape[1] != 3 or post.shape != pre.shape:
        raise ValueError("Expected aligned B×3×H×W PRE/POST")
    if pseudo.shape != (pre.shape[0], 4, *pre.shape[2:]):
        raise ValueError("Expected B×4×H×W pseudo mask")
    if not 0 <= brightness <= .5 or not 0 <= contrast <= .5:
        raise ValueError("Strong jitter parameters must be within [0,0.5]")
    turns = int(torch.randint(4, ()).item())
    weak_pre, weak_post, selected = [torch.rot90(value, turns, (-2, -1))
                                     for value in (pre, post, pseudo)]
    if torch.rand(()).item() < .5:
        weak_pre, weak_post, selected = [value.flip(-1) for value in (weak_pre, weak_post, selected)]
    factor = 1 + (2 * torch.rand(()) - 1) * contrast
    offset = (2 * torch.rand(()) - 1) * brightness
    strong_pre = (weak_pre * factor + offset).clamp(0, 1)
    strong_post = (weak_post * factor + offset).clamp(0, 1)
    return (weak_pre, weak_post), (strong_pre, strong_post), selected
