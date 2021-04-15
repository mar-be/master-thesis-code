import numpy as np

def clip_line_collection(collection, mode):
        for path in collection.get_paths():
            m = (path.vertices[0, 0] + path.vertices[1, 0])/2
            if mode == "left":
                path.vertices[:, 0] = np.clip(path.vertices[:, 0], -np.inf, m)
            else:
                path.vertices[:, 0] = np.clip(path.vertices[:, 0], m, np.inf)

def draw_violins(ax, data, positions, color, widths=12, alpha = 0.5, showmeans=False, mode="left"):
    
    parts = ax.violinplot(data, positions=positions, widths=widths, showmeans=showmeans)

    for pc in parts['bodies']:
         # get the center
        m = np.mean(pc.get_paths()[0].vertices[:, 0])
        # modify the paths to not go further right than the center
        if mode == "left":
            pc.get_paths()[0].vertices[:, 0] = np.clip(pc.get_paths()[0].vertices[:, 0], -np.inf, m)
        else:
            pc.get_paths()[0].vertices[:, 0] = np.clip(pc.get_paths()[0].vertices[:, 0], m, np.inf)
        pc.set_color(color[1])
        # pc.set_facecolor(color[0])
        # pc.set_edgecolor(color[1])

    clip_line_collection(parts['cmins'], mode)
    clip_line_collection(parts['cmaxes'], mode)
    
        
    if showmeans:
        parts['cmeans'].set_color(color[1])
        clip_line_collection(parts['cmeans'], mode)
    
    parts['cbars'].set_color(color[1])
    parts['cbars'].set_alpha(alpha)
    parts['cmins'].set_color(color[1])
    parts['cmins'].set_alpha(alpha)
    parts['cmaxes'].set_color(color[1])
    parts['cmaxes'].set_alpha(alpha)