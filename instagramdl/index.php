<?php
require("../vendor/autoload.php");
require("./config.php");

if (count($argv) > 1) {
    $targetusername = $argv[1];
}

$once = false;
if (count($argv) > 2 and ($argv[2] == "once")) {
    $once = true;
}

#$instagram = new \InstagramAPI\Instagram($username, $password);
$debug = false;
$instagram = new \InstagramAPI\Instagram($debug);
$instagram->setUser($username, $password);

try {
    $instagram->login();
} catch (Exception $e) {
    print($e->getMessage());
    exit();
}

$usernameid = $instagram->getUsernameId($targetusername);

$usernameinfo = $instagram->getUserInfoById($usernameid);
$count = $usernameinfo->user->media_count;

# Get all items
$maxid = null;
$allitems = array();

while (true) {
    $feed = $instagram->getUserFeed($usernameid, $maxid);
    $items = $feed->items;
    //$maxid = end($items)->getMediaId();
    $maxid = $feed->getNextMaxId();
    $allitems = array_merge($allitems, $items);

    fwrite(STDERR, "\r" . count($allitems) . " / " . $count);

    #print($maxid . " " . count($allitems) . " " . $count . "\n");

    if (count($allitems) >= $count or $once) {
        break;
    }
    #break;
}

fwrite(STDERR, "\n");

print(json_encode($allitems));
exit();

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

        "caption_edited" => $item->caption_is_edited(),

        "has_audio" => $item->hasAudio(),
        "duration" => $item->getVideoDuration(),

        "filter_type" => $item->getFilterType(),

        "is_video" => $item->video_versions != null,
        "is_photo" => $item->video_versions == null,

        "images" => array(),
        "videos" => array()
    );

    $caption = $item->getCaption();

    if ($caption) {
        $myobj["caption"] = $item->getCaption()->getText();
    } else {
        $myobj["caption"] = "";
    }

    foreach ($item->image_versions2->candidates as $image) {
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