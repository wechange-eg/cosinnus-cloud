<a id="nextcloud-plattform" href="<?php print_unescaped(\OC::$server->getConfig()->getSystemValue('wechange_plattform_root', '/')); ?>" title="<?php print_unescaped($this->inc('texts/navbar.backtitle')); ?>">
    <div class="logo logo-exit-icon">
        <h1 class="hidden-visually">
            <?php p($theme->getName()); ?> <?php p(!empty($_['application'])?$_['application']: $l->t('Apps')); ?>
        </h1>
    </div>
</a>