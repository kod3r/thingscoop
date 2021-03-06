import cv2
import glob
import multiprocessing
import os
import pydoc
import subprocess
import tempfile

from collections import defaultdict
from progressbar import ProgressBar, Percentage, Bar, ETA

from .classifier import ImageClassifier
from .models import clear_models
from .models import download_model
from .models import get_active_model
from .models import get_all_models
from .models import get_downloaded_models
from .models import info_model
from .models import read_model
from .models import remove_model
from .models import use_model
from .preview import preview
from .query import filename_for_query
from .query import validate_query
from .search import label_video
from .search import search_videos
from .utils import create_supercut
from .utils import search_labels

def main(args):
    model_name = args['--model'] or args['<model>'] or get_active_model()
    
    if args['models']:
        if args['list']:
            models = get_all_models()
            for model in models:
                print "{0}{1}".format(model['name'].ljust(30), model['description'])
        if args['freeze']:
            models = get_downloaded_models()
            for model_name in models:
                print model_name
        elif args['current']:
            print get_active_model()
        elif args['use']:
            use_model(model_name)
        elif args['download']:
            download_model(model_name)
        elif args['info']:
            try:
                model_info = info_model(model_name)
                for key in ['name', 'description', 'dataset']:
                    print "{0}: {1}".format(key.capitalize(), model_info[key])
            except:
                print "Model not found"
        elif args['remove']:
            remove_model(args['<model>'])
        elif args['clear']:
            clear_models()
        return 0

    if args['labels']:
        download_model(model_name)
        model = read_model(model_name)
        labels = sorted(set(model.labels(with_hypernyms=True)), key=lambda l: l.lower())
        if args['list']:
            pydoc.pager('\n'.join(labels))
        elif args['search']:
            search_labels(args['<regexp>'], labels)
        return 0

    sample_rate = float(args['--sample-rate'] or 1)
    min_confidence = float(args['--min-confidence'] or 0.25)
    number_of_words = int(args['--number-of-words'] or 5)
    recreate_index = args['--recreate-index'] or False
    gpu_mode = args['--gpu-mode'] or False

    download_model(model_name)
    model = read_model(model_name)
    classifier = ImageClassifier(model, gpu_mode=gpu_mode, confidence_threshold=min_confidence)
                                 
    if args['preview']:
        preview(args['<file>'], classifier)
        return 0

    if args['index'] or args['describe']:
        timed_labels = label_video(
            args['<file>'],
            classifier,
            sample_rate=sample_rate,
            recreate_index=recreate_index
        )
        if args['describe']:
            freq_dist = defaultdict(lambda: 0)
            for (t, labels) in timed_labels:
                for label in labels:
                    freq_dist[label] += 1
            sorted_labels = sorted(freq_dist.iteritems(), key=lambda (k, v): v, reverse=True)
            print '\n'.join(map(lambda (k, v): "{0} {1}".format(k, v), sorted_labels))
        return 0

    query = args['<query>']
    validate_query(query, model.labels(with_hypernyms=True))
 
    matching_time_regions = search_videos(
        args['<files>'],
        args['<query>'],
        classifier,
        sample_rate=sample_rate,
        recreate_index=recreate_index
    )

    if not matching_time_regions:
        return 0

    if args['search']:
        for filename, region in matching_time_regions:
            start, end = region
            print "%s %f %f" % (filename, start, end)
        return 0

    if args['filter']:
        supercut = create_supercut(matching_time_regions)

        dst = args.get('<dst>')
        if not dst:
            base, ext = os.path.splitext(args['<files>'][0])
            dst = "{0}_filtered_{1}.mp4".format(base, filename_for_query(query))
 
        supercut.to_videofile(
            dst, 
            codec="libx264", 
            temp_audiofile="temp.m4a",
            remove_temp=True,
            audio_codec="aac",
        )

        if args['--open']:
            subprocess.check_output(['open', dst])

