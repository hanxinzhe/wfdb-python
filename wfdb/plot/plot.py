import matplotlib.pyplot as plt
import numpy as np
import os

from ..io.record import Record, rdrecord
from ..io.header import float_types
from ..io._signal import downround, upround


def plotrec(record=None, title=None, annotation=None, time_units='samples',
            sig_style='', ann_style='r*', plot_ann_sym=False, figsize=None,
            return_fig=False, ecg_grids=[]): 
    """ 
    Subplot and label each channel of a WFDB Record.
    Optionally, subplot annotation locations over selected channels.
    
    Input arguments:
    - record: A wfdb Record object. The p_signal attribute will be plotted.
    - title: A string containing the title of the graph.
    - annotation: A list of Annotation objects or numpy arrays. The locations of the Annotation
      objects' 'sample' attribute, or the locations of the numpy arrays' values, will be overlaid on the signals.
      The list index of the annotation item corresponds to the signal channel that each annotation set will be
      plotted on. For channels without annotations to plot, put None in the list. This argument may also be just
      an Annotation object or numpy array, which will be plotted over channel 0.
    - time_units: String specifying the x axis unit. 
      Allowed options are: 'samples', 'seconds', 'minutes', and 'hours'.
    - sig_style: String, or list of strings, specifying the styling of the matplotlib plot for the signals.
      If 'sig_style' is a string, each channel will have the same style. If it is a list, each channel's style will 
      correspond to the list element. ie. sig_style = ['r','b','k']
    - ann_style: String, or list of strings, specifying the styling of the matplotlib plot for the annotations.
      If 'ann_style' is a string, each channel will have the same style. If it is a list, each channel's style will 
      correspond to the list element.
    - plot_ann_sym: Specifies whether to plot the annotation symbols at their locations.
    - figsize: Tuple pair specifying the width, and height of the figure. Same as the 'figsize' argument
      passed into matplotlib.pyplot's figure() function.
    - return_fig: Specifies whether the figure is to be returned as an output argument
    - ecg_grids: List of integers specifying channels in which to plot ecg grids. May be set to [] for
      no channels, or 'all' for all channels. Major grids at 0.5mV, and minor grids at 0.125mV. All channels to be 
      plotted with grids must have units equal to 'uV', 'mV', or 'V'.
    
    Output argument:
    - figure: The matplotlib figure generated. Only returned if the 'return_fig' option is set to True.

    Example Usage:
    import wfdb
    record = wfdb.rdrecord('sampledata/100', sampto=3000)
    annotation = wfdb.rdann('sampledata/100', 'atr', sampto=3000)

    wfdb.plotrec(record, annotation=annotation, title='Record 100 from MIT-BIH Arrhythmia Database', 
                 time_units='seconds', figsize=(10,4), ecg_grids='all')
    """

    # Check the validity of items used to make the plot
    # Return the x axis time values to plot for the record (and annotation if any)
    t, tann, annplot = check_plot_items(record, title, annotation, time_units, sig_style, ann_style)

    siglen, nsig = record.p_signal.shape
    
    # Expand list styles
    if isinstance(sig_style, str):
        sig_style = [sig_style]*record.nsig
    else:
        if len(sig_style) < record.nsig:
            sig_style = sig_style+['']*(record.nsig-len(sig_style))
    if isinstance(ann_style, str):
        ann_style = [ann_style]*record.nsig
    else:
        if len(ann_style) < record.nsig:
            ann_style = ann_style+['r*']*(record.nsig-len(ann_style))

    # Expand ecg grid channels
    if ecg_grids == 'all':
        ecg_grids = range(0, record.nsig)

    # Create the plot  
    fig=plt.figure(figsize=figsize)
    
    for ch in range(nsig):
        # Plot signal channel
        ax = fig.add_subplot(nsig, 1, ch+1)
        ax.plot(t, record.p_signal[:,ch], sig_style[ch], zorder=3) 
        
        if (title is not None) and (ch==0):
            plt.title(title)
            
        # Plot annotation if specified
        if annplot[ch] is not None:
            ax.plot(tann[ch], record.p_signal[annplot[ch], ch], ann_style[ch])
            # Plot the annotation symbols if specified
            if plot_ann_sym:
                for i, s in enumerate(annotation.symbol):
                    ax.annotate(s, (tann[ch][i], record.p_signal[annplot[ch], ch][i]))

        # Axis Labels
        if time_units == 'samples':
            plt.xlabel('index/sample')
        else:
            plt.xlabel('time/'+time_units[:-1])
            
        if record.signame[ch] is not None:
            chanlabel=record.signame[ch]
        else:
            chanlabel='channel'
        if record.units[ch] is not None:
            unitlabel=record.units[ch]
        else:
            unitlabel='NU'
        plt.ylabel(chanlabel+"/"+unitlabel)

        # Show standard ecg grids if specified.
        if ch in ecg_grids:
            
            auto_xlims = ax.get_xlim()
            auto_ylims= ax.get_ylim()

            major_ticks_x, minor_ticks_x, major_ticks_y, minor_ticks_y = calc_ecg_grids(
                auto_ylims[0], auto_ylims[1], record.units[ch], record.fs, auto_xlims[1], time_units)

            min_x, max_x = np.min(minor_ticks_x), np.max(minor_ticks_x)
            min_y, max_y = np.min(minor_ticks_y), np.max(minor_ticks_y)

            for tick in minor_ticks_x:
                ax.plot([tick, tick], [min_y,  max_y], c='#ededed', marker='|', zorder=1)
            for tick in major_ticks_x:
                ax.plot([tick, tick], [min_y, max_y], c='#bababa', marker='|', zorder=2)
            for tick in minor_ticks_y:
                ax.plot([min_x, max_x], [tick, tick], c='#ededed', marker='_', zorder=1)
            for tick in major_ticks_y:
                ax.plot([min_x, max_x], [tick, tick], c='#bababa', marker='_', zorder=2)

            # Plotting the lines changes the graph. Set the limits back
            ax.set_xlim(auto_xlims)
            ax.set_ylim(auto_ylims)

    plt.show(fig)
    
    # Return the figure if requested
    if return_fig:
        return fig

# Calculate tick intervals for ecg grids
def calc_ecg_grids(minsig, maxsig, units, fs, maxt, time_units):

    # 5mm 0.2s major grids, 0.04s minor grids
    # 0.5mV major grids, 0.125 minor grids 
    # 10 mm is equal to 1mV in voltage.
    
    # Get the grid interval of the x axis
    if time_units == 'samples':
        majorx = 0.2*fs
        minorx = 0.04*fs
    elif time_units == 'seconds':
        majorx = 0.2
        minorx = 0.04
    elif time_units == 'minutes':
        majorx = 0.2/60
        minorx = 0.04/60
    elif time_units == 'hours':
        majorx = 0.2/3600
        minorx = 0.04/3600

    # Get the grid interval of the y axis
    if units.lower()=='uv':
        majory = 500
        minory = 125
    elif units.lower()=='mv':
        majory = 0.5
        minory = 0.125
    elif units.lower()=='v':
        majory = 0.0005
        minory = 0.000125
    else:
        raise ValueError('Signal units must be uV, mV, or V to plot the ECG grid.')


    major_ticks_x = np.arange(0, _upround(maxt, majorx)+0.0001, majorx)
    minor_ticks_x = np.arange(0, _upround(maxt, majorx)+0.0001, minorx)

    major_ticks_y = np.arange(downround(minsig, majory), upround(maxsig, majory)+0.0001, majory)
    minor_ticks_y = np.arange(downround(minsig, majory), upround(maxsig, majory)+0.0001, minory)

    return (major_ticks_x, minor_ticks_x, major_ticks_y, minor_ticks_y)

# Check the validity of items used to make the plot
# Return the x axis time values to plot for the record (and time and values for annotation if any)
def check_plot_items(record, title, annotation, time_units, sig_style, ann_style):
    
    # signals
    if not isinstance(record, Record):
        raise TypeError("The 'record' argument must be a valid wfdb.Record object")
    if not isinstance(record.p_signal, np.ndarray) or record.p_signal.ndim != 2:
        raise TypeError("The plotted signal 'record.p_signal' must be a 2d numpy array")
    
    siglen, nsig = record.p_signal.shape

    # fs and time_units
    allowedtimes = ['samples', 'seconds', 'minutes', 'hours']
    if time_units not in allowedtimes:
        raise ValueError("The 'time_units' field must be one of the following: ", allowedtimes)
    # Get x axis values. fs must be valid when plotting time
    if time_units == 'samples':
        t = np.linspace(0, siglen-1, siglen)
    else:
        if not isinstance(record.fs, float_types):
            raise TypeError("The 'fs' field must be a number")
        
        if time_units == 'seconds':
            t = np.linspace(0, siglen-1, siglen)/record.fs
        elif time_units == 'minutes':
            t = np.linspace(0, siglen-1, siglen)/record.fs/60
        else:
            t = np.linspace(0, siglen-1, siglen)/record.fs/3600
    
    # units
    if record.units is None:
        record.units = ['NU']*nsig
    else:
        if not isinstance(record.units, list) or len(record.units)!= nsig:
            raise ValueError("The 'units' parameter must be a list of strings with length equal to the number of signal channels")
        for ch in range(nsig):
            if record.units[ch] is None:
                record.units[ch] = 'NU'

    # signame
    if record.signame is None:
        record.signame = ['ch'+str(ch) for ch in range(1, nsig+1)] 
    else:
        if not isinstance(record.signame, list) or len(record.signame)!= nsig:
            raise ValueError("The 'signame' parameter must be a list of strings, with length equal to the number of signal channels")
    
    # title
    if title is not None and not isinstance(title, str):
        raise TypeError("The 'title' field must be a string")
    
    # signal line style
    if isinstance(sig_style, str):
        pass
    elif isinstance(sig_style, list):
        if len(sig_style) > record.nsig:
            raise ValueError("The 'sig_style' list cannot have more elements than the number of record channels")
    else:
        raise TypeError("The 'sig_style' field must be a string or a list of strings")

    # annotation plot style
    if isinstance(ann_style, str):
        pass
    elif isinstance(ann_style, list):
        if len(ann_style) > record.nsig:
            raise ValueError("The 'ann_style' list cannot have more elements than the number of record channels")
    else:
        raise TypeError("The 'ann_style' field must be a string or a list of strings")


    # Annotations if any
    if annotation is not None:

        # The output list of numpy arrays (or Nones) to plot
        annplot = [None]*record.nsig

        # Move single channel annotations to channel 0
        if isinstance(annotation, annotations.Annotation):
            annplot[0] = annotation.sample
        elif isinstance(annotation, np.ndarray):
            annplot[0] = annotation
        # Ready list.
        elif isinstance(annotation, list):
            if len(annotation) > record.nsig:
                raise ValueError("The number of annotation series to plot cannot be more than the number of channels")
            if len(annotation) < record.nsig:
                annotation = annotation+[None]*(record.nsig-len(annotation))
            # Check elements. Copy over to new list.
            for ch in range(record.nsig):
                if isinstance(annotation[ch], annotations.Annotation):
                    annplot[ch] = annotation[ch].sample
                elif isinstance(annotation[ch], np.ndarray):
                    annplot[ch] = annotation[ch]
                elif annotation[ch] is None:
                    pass
                else:
                    raise TypeError("The 'annotation' argument must be a wfdb.Annotation object, a numpy array, None, or a list of these data types")
        else:
            raise TypeError("The 'annotation' argument must be a wfdb.Annotation object, a numpy array, None, or a list of these data types")
        
        # The annotation locations to plot
        tann = [None]*record.nsig

        for ch in range(record.nsig):
            if annplot[ch] is None:
                continue
            if time_units == 'samples':
                tann[ch] = annplot[ch]
            elif time_units == 'seconds':
                tann[ch] = annplot[ch]/float(record.fs)
            elif time_units == 'minutes':
                tann[ch] = annplot[ch]/float(record.fs)/60
            else:
                tann[ch] = annplot[ch]/float(record.fs)/3600
    else:
        tann = None
        annplot = [None]*record.nsig

    # tann is the sample values to plot for each annotation series
    return (t, tann, annplot)



# Plot the sample locations of a WFDB annotation on a new figure
def plotann(annotation, title = None, time_units = 'samples', return_fig = False): 
    """ Plot sample locations of an Annotation object.
    
    Usage: plotann(annotation, title = None, time_units = 'samples', return_fig = False)
    
    Input arguments:
    - annotation (required): An Annotation object. The sample attribute locations will be overlaid on the signal.
    - title (default=None): A string containing the title of the graph.
    - time_units (default='samples'): String specifying the x axis unit. 
      Allowed options are: 'samples', 'seconds', 'minutes', and 'hours'.
    - return_fig (default=False): Specifies whether the figure is to be returned as an output argument
    
    Output argument:
    - figure: The matplotlib figure generated. Only returned if the 'return_fig' option is set to True.

    Note: The plotrec function is useful for plotting annotations on top of signal waveforms.

    Example Usage:
    import wfdb
    annotation = wfdb.rdann('sampledata/100', 'atr', sampfrom = 100000, sampto = 110000)
    annotation.fs = 360
    wfdb.plotann(annotation, time_units = 'minutes')
    """

    # Check the validity of items used to make the plot
    # Get the x axis annotation values to plot
    plotvals = checkannplotitems(annotation, title, time_units)
    
    # Create the plot
    fig=plt.figure()
    
    plt.plot(plotvals, np.zeros(len(plotvals)), 'r+')
    
    if title is not None:
        plt.title(title)
        
    # Axis Labels
    if time_units == 'samples':
        plt.xlabel('index/sample')
    else:
        plt.xlabel('time/'+time_units[:-1])

    plt.show(fig)
    
    # Return the figure if requested
    if return_fig:
        return fig

# Check the validity of items used to make the annotation plot
def checkannplotitems(annotation, title, time_units):
    
    # signals
    if not isinstance(annotation, annotations.Annotation):
        raise TypeError("The 'annotation' field must be a 'wfdb.Annotation' object")

    # fs and time_units
    allowedtimes = ['samples', 'seconds', 'minutes', 'hours']
    if time_units not in allowedtimes:
        raise ValueError("The 'time_units' field must be one of the following: ", allowedtimes)

    # fs must be valid when plotting time
    if time_units != 'samples':
        if not isinstance(annotation.fs, float_types):
            raise Exception("In order to plot time units, the Annotation object must have a valid 'fs' attribute")

    # Get x axis values to plot
    if time_units == 'samples':
        plotvals = annotation.sample
    elif time_units == 'seconds':
        plotvals = annotation.sample/float(annotation.fs)
    elif time_units == 'minutes':
        plotvals = annotation.sample/float(annotation.fs*60)
    elif time_units == 'hours':
        plotvals = annotation.sample/float(annotation.fs*3600)

    # title
    if title is not None and not isinstance(title, str):
        raise TypeError("The 'title' field must be a string")
    
    return plotvals


def plot_records(directory=os.getcwd()):
    """
    Plot all wfdb records in a directory (by finding header files)
    """
    filelist = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    filelist = [f for f in filelist if f.endswith('.hea')]
    recordlist = [f.split('.hea')[0] for f in filelist]
    recordlist.sort()

    for record_name in recordlist:
        record = records.rdrecord(record_name)

        plotrec(record, title='Record: %s' % record.recordname)
        input('Press enter to continue...')
