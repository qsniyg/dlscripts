<?php
require("../vendor/autoload.php");
require("./config.php");

if (count($argv) > 1) {
    $targetusername = $argv[1];
}

$instagram = new \InstagramAPI\Instagram($username, $password);

try {
    $instagram->login();
} catch (Exception $e) {
    print($e->getMessage());
    exit();
}

$usernameid = $instagram->getUsernameId($targetusername);

$usernameinfo = $instagram->getUsernameInfo($usernameid);
$count = $usernameinfo->getMediaCount();

# Get all items
$maxid = null;
$allitems = array();

while (true) {
    $feed = $instagram->getUserFeed($usernameid, $maxid);
    $items = $feed->getItems();
    $maxid = end($items)->getMediaId();
    $allitems = array_merge($allitems, $items);

    fwrite(STDERR, "\r" . count($allitems) . " / " . $count);

    #print($maxid . " " . count($allitems) . " " . $count . "\n");

    if (count($allitems) >= $count) {
        break;
    }
    #break;
}

fwrite(STDERR, "\n");

$thejson = array();

foreach ($allitems as $i => $item) {
    #$date = new DateTime("@" . $item->getTakenAt(), new DateTimeZone("UTC"));
    #$taken_at = $date->getTimestamp() + $tz->getOffset($date);
    $taken_at = $item->getTakenAt();

    $myobj = array(
        "username" => $targetusername,

        "taken_at" => $taken_at,
        "device_timestamp" => $item->getDeviceTimestamp(),

        "original_width" => $item->getOriginalWidth(),
        "original_height" => $item->getOriginalHeight(),

        "caption_edited" => $item->isCaptionEdited(),

        "has_audio" => $item->hasAudio(),
        "duration" => $item->getVideoDuration(),

        "filter_type" => $item->getFilterType(),

        "is_video" => $item->isVideo(),
        "is_photo" => $item->isPhoto(),

        "images" => array(),
        "videos" => array()
    );

    $caption = $item->getCaption();

    if ($caption) {
        $myobj["caption"] = $item->getCaption()->getText();
    } else {
        $myobj["caption"] = "";
    }

    foreach ($item->getImageVersions() as $image) {
        $imageobj = array(
            "url" => $image->getUrl(),
            "width" => $image->getWidth(),
            "height" => $image->getHeight()
        );

        if ($image->getWidth() == $item->getOriginalWidth() &&
            $image->getHeight() == $item->getOriginalHeight()) {
            $myobj["image"] = $imageobj;
        }

        array_push($myobj["images"], $imageobj);
    }

    $videos = $item->getVideoVersions();
    if ($videos) {
        foreach ($videos as $video) {
            $videoobj = array(
                "url" => $video->getUrl(),
                "type" => $video->getType(),
                "width" => $video->getWidth(),
                "height" => $video->getHeight()
            );

            array_push($myobj["videos"], $videoobj);
        }
    }

    array_push($thejson, $myobj);
}

print(json_encode($thejson));
#print($feed->getNumResults());
?>