import numpy as np
import cv2
import random
import argparse
from argparse import RawTextHelpFormatter

# provided styles
IMPRESSIONIST = [100, [8,4,2], 1, .5, 1, 1, 4, 16]
EXPRESSIONIST = [50, [8,4,2], .25, 0.5, 0.7, 1, 10, 16] # jitter jv = 0.5
COLORIST_WASH = [200, [8,4,2], 1, 0.5, 0.5, 1, 4, 16] # jr=jg=jb=0.3
POINTILLIST = [100, [4,2], 1, 0.5, 0.1, 0.5, 0, 0] # jv=1, jh=0.3

class painterlybrush:
    def __init__(self):
        self.results = {}
    
    def paint(self, sourceImg, T, R, fc, fs, a, fg, minl, maxl, retList=0):
        self.canvas = np.zeros(sourceImg.shape, dtype=int)
        self.canvas.fill(4534534245.)
        self.T = T # approximation threshold
        self.R = R # brush radii
        self.fc = fc # curvature filter, limit or exaggerate stroke curvature
        self.fs = fs # blur factor
        self.a = a # opacity for paint, between 0 and 1
        self.fg = fg # grid size, controls spacing of brush strokes (fg*Ri = step size in paint layer)
        self.minl = minl # smallest stroke length
        self.maxl = maxl # largest stroke length
            
        for ri in R: # For brush radius ri
            sigma = fs * ri
            refImg = np.asarray(cv2.GaussianBlur(sourceImg,(0,0),sigmaX = sigma))
            self.paintLayer(refImg, ri)
            self.results["After brush size " + str(ri)] = self.canvas/255
        if retList == 1:
            return self.results
        return self.canvas

    def paintLayer(self, refImg, R):
        # List of strokes
        S = []

        D = np.sqrt(np.sum((self.canvas-refImg)**2, axis=2))
        #D = self.color_diff(self.canvas, refImg)

        grid = int(self.fg * R) # fg*Ri = step size in paint layer

        numRow, numCol, numCh = refImg.shape
        # Wait! Paper specifies to use luminance for sobel, so YIQ instead of HSV
        #ref_hsv = cv2.cvtColor(refImg, cv2.COLOR_BGR2HSV)
        #val = ref_hsv[:,:,2]
        
        val = (refImg[:, :, 0] * 0.11) + (refImg[:, :, 1] * 0.59) + (refImg[:, :, 2] * 0.20)
        
        self.sobelx = cv2.Sobel(val,cv2.CV_64F,1,0,ksize=3)
        self.sobely = cv2.Sobel(val,cv2.CV_64F,0,1,ksize=3)
        
        self.gradientMag = np.abs(np.sqrt(self.sobelx**2 + self.sobely**2))
        
        # Save the results
        self.results["Sobel filter for brush size " + str(R)] = self.gradientMag/255
        
        
        for x in range(0, numRow, grid):
            for y in range(0, numCol, grid):
                
                #M = D[ max(int((x-grid)//2), 0) : int((x+grid)//2),
                #  int(max((y-grid)//2), 0) : int((y+grid)//2)]
                M = D[x:x+grid, y:y+grid]
                areaError = M.sum() / (grid**2)
                
                if areaError > self.T:
                    x1, y1 = x, y
                    largeIndex = np.argmax(M, axis=None)
                    regionIndex = np.unravel_index(largeIndex, M.shape)
                    x1 += regionIndex[0]
                    y1 += regionIndex[1]
                    s = self.makeSplineStroke(x1, y1, R, refImg)
                    S.append(s)

        # paint all strokes in S on canvas in random order
        r = list(range(len(S)))
        random.shuffle(r)
        self.canvas = (self.canvas).astype(np.uint8)
        for i in r:
            # S is list of strokes small s, each small s is a list of points (x, y)
            # with each point to be painted on canvas with color of refImg[s[0]], since
            # the first point x0 y0 is the stroke color of the stroke
            s = S[i]
            stroke_color = refImg[s[0]]/255
            stroke_color = stroke_color*255
            for i in range(1, len(s)):
                coordss = s[i]
                cv2.circle(self.canvas,(coordss[1], coordss[0]), R, stroke_color, -1)
        #sigma = self.fs * R
        sigma = R

        # Minimize circle apperance by blurring the brush strokes
        self.canvas = np.asarray(cv2.GaussianBlur(self.canvas,(3,3),sigmaX = sigma))
        #self.canvas = np.asarray(cv2.GaussianBlur(self.canvas,(5,5),0))
        self.canvas = (self.canvas).astype(int)
                

    def makeSplineStroke(self, x0,y0,R,refImg):
        numRow, numCol, numCh = self.canvas.shape
        if (x0 >= numRow) or (y0 >= numCol):
                return
        
        strokeColor = refImg[x0,y0]
        # K = a new stroke with radius R and color strokeColor
        K = []
        K.append((x0, y0))
        x, y = x0, y0

        lastDx, lastDy = 0,0


        for i in range(0,self.maxl+1):
            
            if((i > self.minl) and (self.color_diff(refImg[x,y], \
             self.canvas[x,y]) < self.color_diff(refImg[x,y], strokeColor))):
            
                return K

            # detect vanishing gradient   
            if(self.gradientMag[x, y] == 0):
                return K

            # get unit vector of gradient
            #gx, gy = refImg.graidentDirection(x, y)
            gy, gx = self.sobelx[x,y], self.sobely[x,y]
            
            # compute a normal direction
            dx, dy = -gy, gx

            # if necessary, reverse direction
            if(lastDx * dx + lastDy * dy < 0):
                dx, dy = -dx, -dy
            
            # filter the stroke direction
            dx = self.fc * dx + (1-self.fc) * (lastDx)
            dy = self.fc * dy + (1-self.fc) * (lastDy)

            dx = dx / np.sqrt(dx**2 + dy**2)
            dy = dy / np.sqrt(dx**2 + dy**2)

            x, y = (int(x+R*dx), int(y+R*dy))
            
            
            if (x >= numRow) or (y >= numCol):
                return K
            lastDx, lastDy = dx, dy

            # add the point (x,y) to K
            K.append((x,y))
            
        return K

    def color_diff(self, color1, color2):
        # require RGB order
        # defined as |(r1, g1, b1) - (r2,g2,b2)| = ((r1-r2)^2 + (g1-g2)^2 + (b1-b2)^2)^(1/2)

        r_diff = float(color1[0]) - float(color2[0])
        g_diff = float(color1[1]) - float(color2[1])
        b_diff = float(color1[2]) - float(color2[2])

        return np.sqrt(r_diff**2 + g_diff**2 + b_diff**2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Render a painterly image. \
     \nA python implementation of "Painterly Rendering with Curved Brush Strokes \
      of Multiple Sizes" by Aaron Hertzmann.', formatter_class=RawTextHelpFormatter)
    group = parser.add_mutually_exclusive_group() #(required=True)
    group2 = parser.add_argument_group('manually specified parameters')
    parser.add_argument('--input', '-i', metavar='INPUTFILE', required=True, type=str, \
    nargs=1, help='path to the input image')
    parser.add_argument('--out', '-o', metavar='OUTPUTFILE', required=True, type=str, \
    nargs=1, help='path to the output image destination')
    
    group2.add_argument('-t', '-T', metavar='T', type=int, nargs=1, \
    help='approximation threshold, painting similarity to source')
    
    group2.add_argument('-fc', metavar='fc', type =float, nargs=1,\
     help='curvature filter, stroke curvature limit')
    group2.add_argument('-fs', metavar='fs', type=float, nargs=1, help='blur factor, blur kernel size')
    group2.add_argument('-op', '-a', metavar='alpha', type=float, nargs=1, help='opacity, paint opacity')
    group2.add_argument('-fg', metavar='fg', type=float, nargs=1, help='grid size')
    group2.add_argument('-min', '-minl', metavar='minl', type=int, nargs=1, help='minimum brush length')
    group2.add_argument('-max', '-maxl', metavar='maxl', type=int, nargs=1, help='maximum brush length')
    group2.add_argument('--brushes', '-ri', metavar='Ri', type=int, nargs='*', help='list of brush sizes')

    group.add_argument("--impressionist", action="store_true", help="normal painting style")
    group.add_argument("--expressionist", action="store_true", help="elongated brush strokes")
    group.add_argument("--colorist_wash", action="store_true", \
    help="loose and semi-transparent brush strokes")
    group.add_argument("--pointillist", action="store_true", help="densely-placed circles")


    args = parser.parse_args()

    params = []
    if args.impressionist:
        params = IMPRESSIONIST
    elif args.expressionist:
        params = EXPRESSIONIST
    elif args.colorist_wash:
        params = COLORIST_WASH
    elif args.pointillist:
        params = POINTILLIST
    else:
        params = [args.t[0], [*args.brushes], args.fc[0], args.fs[0], args.op[0], args.fg[0], \
         args.min[0], args.max[0]]
    print("Style Parameters: " + "T=" + str(params[0]), ", R=" + str(params[1]) 
    + ", fc=" + str(params[2]) + ", fs=" + str(params[3]) + ", alpha=" + str(params[4])
     + ", fg=" + str(params[5]) + ", minl=" + str(params[6]) + ", maxl=" + str(params[7]))
    print("Rendering image...")

    sourceImg = cv2.imread(args.input[0])
    painter = painterlybrush()
    res = painter.paint(sourceImg, *params)
    cv2.imwrite(args.out[0], res)
    
    print("Done!" + " Saved to " + str(args.out[0]))


    