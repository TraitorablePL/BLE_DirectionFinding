import math
import cmath
import json
import numpy as np

class Localization():

    def __init__(self):
        self.velocity = 299702547 # m/s
        self.d = 0.05 # m, distance between antennas

    def toPlusMinusPI(self, angle):
        while angle >= 180:
            angle -= 2 * 180
        while angle < -180:
            angle += 2 * 180
        return angle

    def calcMean(self, values):
        if len(values) == 0:
            return 0
        else:
            return sum(values)/len(values)

    def calcAngle(self, deg_value, inverted, results, frequency):
        wave_len = self.velocity/frequency
        output = 0
        try:
            result = math.acos((np.deg2rad(deg_value)*wave_len)/(2*math.pi*self.d))
        except ValueError:
            pass
        else:
            if inverted:
                output = abs(self.toPlusMinusPI(np.rad2deg(result)+180))
            else:
                output = abs(self.toPlusMinusPI(np.rad2deg(result)))
        results.append(output)

    def channel2Freq(self, channel):
        frequency = 2450 #MHz
        if(channel <= 10):
            frequency = 2404 + channel*2
        elif(channel < 37):
            frequency = 2428 + (channel-11)*2
        elif(channel == 37):
            frequency = 2402
        elif(channel == 38):
            frequency = 2426
        else:
            frequency = 2480
        return frequency * 1000000

    ## Basic algorithm for localization
    def locate_basic(self, data):
        IQ = []
        # Iterate through each IQ sample to normalize it 
        for elem in data["IQ"]:
            I = elem[0]/128 if elem[0] < 0 else elem[0]/127
            Q = elem[1]/128 if elem[1] < 0 else elem[1]/127
            IQ.append(complex(I,Q))

        ref_period_diff = []
        samp_period_diff = []
        ref_mean_diff = 0

        # Iterate through each sample (82) in one connection event 
        for i in range(len(IQ)-1):
            # Phase calculation from IQ samples
            phase_current = np.rad2deg(np.arctan2(IQ[i].imag, IQ[i].real))
            phase_next = np.rad2deg(np.arctan2(IQ[i + 1].imag, IQ[i + 1].real))

            if (i < 7):
                ref_period_diff.append(abs(self.toPlusMinusPI(phase_next - phase_current)))
            elif (i == 7):
                ref_mean_diff = self.calcMean(ref_period_diff)
            else:
                # 2*ref_mean_diff as a in ref period sample is taken twice as fast as in sampling period, 
                # so it needs to be doubled
                samp_period_diff.append(self.toPlusMinusPI((phase_next - phase_current) - 2*ref_mean_diff))

        azimuth = []
        elevation = []
        inverted = False
        horizontal = True

        # Calculate direction angles
        for i in range(len(samp_period_diff)-1):
            # Skip corner differences samples
            if ((i + 1) % 4 == 0):
                if(not horizontal): 
                    # Change to inverted after 2 sections of non inverted data due to opposite scanning direction
                    inverted = not inverted
                # Change orientation after each section 
                horizontal = not horizontal
            else:
                if (horizontal):
                    self.calcAngle(samp_period_diff[i], inverted, azimuth, self.channel2Freq(data["Channel"]))
                else:
                    self.calcAngle(samp_period_diff[i], inverted, elevation, self.channel2Freq(data["Channel"]))

        return (self.calcMean(azimuth), self.calcMean(elevation))
      
    ## MUSIC algorithm for localization
    def locate_MUSIC(self):
        pass
