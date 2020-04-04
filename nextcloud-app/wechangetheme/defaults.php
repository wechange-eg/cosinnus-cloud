<?php

class OC_Theme {

	/**
     * Returns the base URL
     * @return string URL
     */
    public function getBaseUrl() {
        return 'https://nextcloud.plattform-n.staging.wechange.de';
    }
    
    /**
     * Returns the base URL
     * TODO: Not working right now.
     * @return string URL
     */
    public function getPlattformBaseUrl() {
        return 'https://nextcloud.plattform-n.staging.wechange.de';
    }

	/**
	 * Returns the documentation URL
	 * @return string URL
	 */
	public function getDocBaseUrl() {
		return 'https://docs.nextcloud.com';
	}

	/**
	 * Returns the title
	 * @return string title
	 */
	public function getTitle() {
		return 'n Cloud';
	}

	/**
     * Returns the short name of the software
     * @return string title
     */
    public function getName() {
        return 'plattform n Cloud';
    }
    
	/**
	 * Returns the short name of the software containing HTML strings
	 * @return string title
	 */
	public function getHTMLName() {
		return 'n Cloud';
	}

	/**
	 * Returns entity (e.g. company name) - used for footer, copyright
	 * @return string entity name
	 */
	public function getEntity() {
		return 'netzwerk n';
	}

	/**
	 * Returns slogan
	 * @return string slogan
	 */
	public function getSlogan() {
		return '';
	}

	/**
	 * Returns logo claim
	 * @return string logo claim
	 * @deprecated 13.0.0 not used anymore
	 */
	public function getLogoClaim() {
		return '';
	}

	/**
	 * Returns short version of the footer
	 * @return string short footer
	 */
	public function getShortFooter() {
		$footer = '© ' . date('Y') . ' <a href="' . $this->getBaseUrl() . '" target="_blank">' . $this->getEntity() . '</a>';
		return $footer;
	}

	/**
	 * Returns long version of the footer
	 * @return string long footer
	 */
	public function getLongFooter() {
		$footer = '© ' . date('Y') . ' <a href="' . $this->getBaseUrl() . '" target="_blank">' . $this->getEntity() . '</a>';
		return $footer;
	}

	/**
	 * Generate a documentation link for a given key
	 * @return string documentation link
	 */
	public function buildDocLinkToKey($key) {
		return $this->getDocBaseUrl() . '/server/15/go.php?to=' . $key;
	}


	/**
	 * Returns mail header color
	 * @return string
	 */
	public function getColorPrimary() {
		return '#0082C9';
	}

	/**
	 * Returns variables to overload defaults from core/css/variables.scss
	 * @return array
	 */
	public function getScssVariables() {
		return [
			'color-primary' => '#0082C9'
		];
	}
	

}
